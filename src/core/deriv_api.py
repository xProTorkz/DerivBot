"""
Cliente centralizado para a nova API da Deriv (Single PAT + OTP WebSocket Flow)
Conforme especificação do Issue #15:
- 1 PAT -> GET contas -> escolher account_id -> gerar OTP -> conectar WebSocket
- Sem envio de authorize legado
- Sanitização rigorosa de credenciais e tokens em logs e exceções
"""

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger("DerivBot.DerivAPI")


class DerivAPIError(Exception):
    """Exceção base para erros na API Deriv."""
    pass


class DerivAuthError(DerivAPIError):
    """Erro 401: Token PAT inválido ou não autorizado."""
    pass


class DerivPermissionError(DerivAPIError):
    """Erro 403: Escopo/permissão insuficiente (trade requerido)."""
    pass


class DerivAccountNotFoundError(DerivAPIError):
    """Erro de conta não encontrada ou tipo desejado ausente."""
    pass


def sanitizar_url_ws(url: str) -> str:
    """Remove o parâmetro de OTP da URL para logging seguro."""
    if not url:
        return ""
    # Substitui ?otp=... ou &otp=... por placeholder
    return re.sub(r'([?&]otp=)[^&]+', r'\1[PROTEGIDO]', url)


class DerivAPIClient:
    """Cliente HTTP REST oficial para gestão de contas e geração de OTP da Deriv."""

    BASE_URL = "https://api.derivws.com"

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or self.BASE_URL).rstrip("/")

    def listar_contas(self, pat: str, app_id: str) -> List[Dict[str, Any]]:
        """
        Consulta as contas vinculadas ao PAT via REST oficial.
        GET /trading/v1/options/accounts
        """
        if not app_id or not str(app_id).strip():
            raise ValueError("DERIV_APP_ID não configurado")
        if not pat or not str(pat).strip():
            raise ValueError("Token PAT da Deriv não configurado")

        url = f"{self.base_url}/trading/v1/options/accounts"
        headers = {
            "Authorization": f"Bearer {pat.strip()}",
            "Deriv-App-ID": str(app_id).strip(),
            "Accept": "application/json",
            "User-Agent": "DerivBot/2.0",
        }

        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
                raw_accounts = payload.get("data", [])

                contas_processadas: List[Dict[str, Any]] = []
                for acc in raw_accounts:
                    tipo_bruto = str(acc.get("account_type", "")).lower().strip()
                    # Classificação rigorosa: demo -> DEMO, real -> REAL
                    tipo_normalizado = "demo" if tipo_bruto == "demo" else "real"
                    
                    try:
                        saldo_num = float(acc.get("balance", 0.0))
                    except (ValueError, TypeError):
                        saldo_num = 0.0

                    contas_processadas.append({
                        "account_id": str(acc.get("account_id", "")).strip(),
                        "account_type": tipo_normalizado,
                        "status": str(acc.get("status", "active")).lower().strip(),
                        "currency": str(acc.get("currency", "USD")).upper().strip(),
                        "balance": saldo_num,
                    })

                logger.info(
                    f"Contas localizadas com sucesso: {len(contas_processadas)} "
                    f"(Demo: {sum(1 for c in contas_processadas if c['account_type'] == 'demo')}, "
                    f"Real: {sum(1 for c in contas_processadas if c['account_type'] == 'real')})"
                )
                return contas_processadas

        except urllib.error.HTTPError as e:
            self._tratar_erro_http(e)
            return []
        except urllib.error.URLError as e:
            logger.error(f"Erro de conexão com API Deriv: {e.reason}")
            raise DerivAPIError(f"Falha na comunicação de rede com Deriv: {e.reason}")

    def solicitar_otp(self, pat: str, app_id: str, account_id: str) -> str:
        """
        Gera um OTP de uso único para a conta selecionada e retorna a URL do WebSocket.
        POST /trading/v1/options/accounts/{accountId}/otp
        """
        if not app_id or not str(app_id).strip():
            raise ValueError("DERIV_APP_ID não configurado")
        if not pat or not str(pat).strip():
            raise ValueError("Token PAT da Deriv não configurado")
        if not account_id or not str(account_id).strip():
            raise ValueError("account_id não informado para solicitação de OTP")

        url = f"{self.base_url}/trading/v1/options/accounts/{account_id.strip()}/otp"
        headers = {
            "Authorization": f"Bearer {pat.strip()}",
            "Deriv-App-ID": str(app_id).strip(),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "DerivBot/2.0",
        }

        req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
                ws_url = payload.get("data", {}).get("url")

                if not ws_url:
                    raise DerivAPIError("Resposta da API Deriv não contém a URL WebSocket autenticada (data.url ausente).")

                logger.info(f"Novo OTP gerado com sucesso para conta {account_id} -> {sanitizar_url_ws(ws_url)}")
                return ws_url

        except urllib.error.HTTPError as e:
            self._tratar_erro_http(e, account_id=account_id)
            return ""
        except urllib.error.URLError as e:
            logger.error(f"Erro de rede ao solicitar OTP para conta {account_id}: {e.reason}")
            raise DerivAPIError(f"Falha na comunicação de rede com Deriv ao solicitar OTP: {e.reason}")

    def selecionar_conta_padrao(
        self,
        contas: List[Dict[str, Any]],
        preferir_real: bool = False,
        account_id_especifico: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Seleciona a conta adequada.
        Por segurança e governança:
        - Se preferir_real=False (padrão): seleciona a conta Demo ativa. NUNCA muda silenciosamente para Real!
        - Se preferir_real=True: seleciona conta Real. Se não existir, erro explícito.
        """
        if not contas:
            raise DerivAccountNotFoundError("Nenhuma conta disponível vinculada a este token PAT.")

        if account_id_especifico:
            for acc in contas:
                if acc["account_id"] == account_id_especifico:
                    return acc
            raise DerivAccountNotFoundError(f"Conta com ID '{account_id_especifico}' não encontrada na listagem.")

        if not preferir_real:
            # Busca demo ativa prioritariamente
            demo_ativas = [c for c in contas if c["account_type"] == "demo" and c.get("status") == "active"]
            if demo_ativas:
                return demo_ativas[0]
            
            # Busca qualquer demo
            todas_demos = [c for c in contas if c["account_type"] == "demo"]
            if todas_demos:
                return todas_demos[0]

            # REGRA INVIOLÁVEL: Não mudar silenciosamente para Real!
            raise DerivAccountNotFoundError("Nenhuma conta Demo vinculada foi encontrada no token PAT.")

        else:
            # Conta Real explícita solicitada pelo usuário
            real_ativas = [c for c in contas if c["account_type"] == "real" and c.get("status") == "active"]
            if real_ativas:
                return real_ativas[0]

            todas_reais = [c for c in contas if c["account_type"] == "real"]
            if todas_reais:
                return todas_reais[0]

            raise DerivAccountNotFoundError("Nenhuma conta Real vinculada foi encontrada no token PAT.")

    def _tratar_erro_http(self, e: urllib.error.HTTPError, account_id: Optional[str] = None):
        """Sanitiza e traduz erros HTTP da Deriv para exceções claras e amigáveis."""
        status_code = e.code
        corpo = ""
        try:
            corpo = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass

        msg_api = ""
        try:
            parsed = json.loads(corpo)
            if isinstance(parsed, dict):
                msg_api = parsed.get("error", {}).get("message") or parsed.get("message") or ""
        except Exception:
            pass

        if status_code == 401:
            raise DerivAuthError("Token PAT inválido ou não autorizado.")
        elif status_code == 403:
            raise DerivPermissionError("O token não possui a permissão necessária (trade).")
        elif status_code == 404:
            alvo = f" '{account_id}'" if account_id else ""
            raise DerivAccountNotFoundError(f"Conta{alvo} não encontrada na Deriv.")
        elif status_code == 429:
            raise DerivAPIError("Limite de requisições excedido na Deriv (rate limit). Tente novamente em alguns instantes.")
        elif 500 <= status_code <= 599:
            raise DerivAPIError(f"Serviço da Deriv temporariamente indisponível (HTTP {status_code}).")
        else:
            detalhe = f": {msg_api}" if msg_api else ""
            raise DerivAPIError(f"Erro na requisição Deriv (HTTP {status_code}){detalhe}")
