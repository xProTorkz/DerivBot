"""
Testes Unitários Automatizados para Autenticação Deriv (Single PAT + WebSocket OTP)
Issue #15 — Validação completa de fluxos, mocks e governança de segurança
"""

import io
import json
import logging
import os
import sys
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

# Adiciona raiz do projeto ao path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.core.deriv_api import (
    DerivAPIClient,
    DerivAPIError,
    DerivAuthError,
    DerivPermissionError,
    DerivAccountNotFoundError,
    sanitizar_url_ws,
)
from src.core.motor import Motor


class TestDerivAuth(unittest.TestCase):
    """Suíte de testes para autenticação PAT único e conexão OTP WebSocket."""

    def setUp(self):
        self.client = DerivAPIClient(base_url="https://api.derivws.com")
        self.mock_pat = "mock_pat_token_test_12345"
        self.mock_app_id = "mock_app_99999"

    # 1. PAT retornando Demo + Real
    @patch("urllib.request.urlopen")
    def test_pat_retornando_demo_e_real(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": [
                {
                    "account_id": "DOT123456",
                    "account_type": "demo",
                    "status": "active",
                    "currency": "USD",
                    "balance": 10000.0,
                },
                {
                    "account_id": "ROT987654",
                    "account_type": "real",
                    "status": "active",
                    "currency": "USD",
                    "balance": 150.50,
                },
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        contas = self.client.listar_contas(self.mock_pat, self.mock_app_id)
        self.assertEqual(len(contas), 2)
        tipos = [c["account_type"] for c in contas]
        self.assertIn("demo", tipos)
        self.assertIn("real", tipos)
        self.assertEqual(contas[0]["account_id"], "DOT123456")
        self.assertEqual(contas[1]["account_id"], "ROT987654")

    # 2. Seleção Demo padrão
    def test_selecao_demo_padrao(self):
        contas = [
            {"account_id": "ROT987654", "account_type": "real", "status": "active", "balance": 100.0},
            {"account_id": "DOT123456", "account_type": "demo", "status": "active", "balance": 10000.0},
        ]
        conta = self.client.selecionar_conta_padrao(contas, preferir_real=False)
        self.assertEqual(conta["account_type"], "demo")
        self.assertEqual(conta["account_id"], "DOT123456")

    # 3. Real NUNCA selecionada silenciosamente quando se busca Demo
    def test_real_nunca_selecionada_silenciosamente(self):
        contas = [
            {"account_id": "ROT987654", "account_type": "real", "status": "active", "balance": 100.0},
        ]
        # Se preferir_real=False e só houver conta Real, DEVE disparar erro e nunca selecionar Real
        with self.assertRaises(DerivAccountNotFoundError):
            self.client.selecionar_conta_padrao(contas, preferir_real=False)

    # 4. Geração de OTP por account_id
    @patch("urllib.request.urlopen")
    def test_geracao_otp_por_account_id(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "data": {
                "url": "wss://ws.derivws.com/websockets/v3?app_id=mock_app_99999&otp=sample_otp_token_xyz"
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        ws_url = self.client.solicitar_otp(self.mock_pat, self.mock_app_id, "DOT123456")
        self.assertIn("wss://", ws_url)
        self.assertIn("sample_otp_token_xyz", ws_url)

        # Valida que o request foi montado com a URL e headers corretos
        req = mock_urlopen.call_args[0][0]
        self.assertTrue(req.get_full_url().endswith("/trading/v1/options/accounts/DOT123456/otp"))
        self.assertEqual(req.headers.get("Authorization"), f"Bearer {self.mock_pat}")
        self.assertEqual(req.headers.get("Deriv-app-id"), self.mock_app_id)

    # 5. Reconexão gera OTP novo
    @patch.object(DerivAPIClient, "solicitar_otp")
    @patch.object(DerivAPIClient, "listar_contas")
    def test_reconexao_gera_otp_novo(self, mock_listar, mock_otp):
        mock_listar.return_value = [
            {"account_id": "DOT123456", "account_type": "demo", "status": "active", "balance": 10000.0}
        ]
        mock_otp.side_effect = [
            "wss://ws.derivws.com/websockets/v3?otp=otp_primeira_conexao",
            "wss://ws.derivws.com/websockets/v3?otp=otp_segunda_conexao_reconnect",
        ]

        def fake_ws(*args, **kwargs):
            mock_ws = MagicMock()
            on_open = kwargs.get("on_open")
            mock_ws.run_forever = lambda: on_open(mock_ws) if on_open else None
            return mock_ws

        motor = Motor()
        motor.app_id = self.mock_app_id
        with patch("websocket.WebSocketApp", side_effect=fake_ws):
            conectado = motor.conectar(token=self.mock_pat, account_id="DOT123456", account_type="demo", app_id=self.mock_app_id)
            self.assertTrue(conectado)
            self.assertEqual(mock_otp.call_count, 1)

            # Simula reconexão que deve gerar novo OTP
            url_reconnect = motor._obter_nova_url_ws_autenticada()
            self.assertIn("otp_segunda_conexao_reconnect", url_reconnect)
            self.assertEqual(mock_otp.call_count, 2)

    # 6. WebSocket não envia mais 'authorize'
    @patch.object(DerivAPIClient, "solicitar_otp")
    @patch.object(DerivAPIClient, "listar_contas")
    def test_websocket_nao_envia_authorize(self, mock_listar, mock_otp):
        mock_listar.return_value = [
            {"account_id": "DOT123456", "account_type": "demo", "status": "active", "balance": 10000.0}
        ]
        mock_otp.return_value = "wss://ws.derivws.com/websockets/v3?otp=test_otp"

        motor = Motor()
        motor.app_id = self.mock_app_id
        mensagens_enviadas = []

        def fake_ws(*args, **kwargs):
            mock_ws = MagicMock()
            mock_ws.send.side_effect = lambda msg: mensagens_enviadas.append(json.loads(msg))
            on_open = kwargs.get("on_open")
            mock_ws.run_forever = lambda: on_open(mock_ws) if on_open else None
            return mock_ws

        with patch("websocket.WebSocketApp", side_effect=fake_ws):
            conectado = motor.conectar(token=self.mock_pat, account_id="DOT123456", account_type="demo", app_id=self.mock_app_id)
            self.assertTrue(conectado)

            # Verifica mensagens enviadas: NUNCA deve conter "authorize"
            self.assertTrue(len(mensagens_enviadas) > 0)
            for msg in mensagens_enviadas:
                self.assertNotIn("authorize", msg, "Erro: 'authorize' legado foi enviado pelo novo fluxo!")

    # 7. Erro 401 do PAT (Token inválido ou não autorizado)
    @patch("urllib.request.urlopen")
    def test_erro_401_pat_invalido(self, mock_urlopen):
        http_error = urllib.error.HTTPError(
            url="https://api.derivws.com/trading/v1/options/accounts",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(b'{"error": {"message": "Invalid token"}}')
        )
        mock_urlopen.side_effect = http_error

        with self.assertRaises(DerivAuthError) as ctx:
            self.client.listar_contas(self.mock_pat, self.mock_app_id)
        self.assertIn("Token PAT inválido ou não autorizado.", str(ctx.exception))

    # 8. Erro 403 de escopo/permissão insuficiente (trade requerido)
    @patch("urllib.request.urlopen")
    def test_erro_403_scope_insuficiente(self, mock_urlopen):
        http_error = urllib.error.HTTPError(
            url="https://api.derivws.com/trading/v1/options/accounts",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=io.BytesIO(b'{"error": {"message": "Scope trade required"}}')
        )
        mock_urlopen.side_effect = http_error

        with self.assertRaises(DerivPermissionError) as ctx:
            self.client.listar_contas(self.mock_pat, self.mock_app_id)
        self.assertIn("O token não possui a permissão necessária (trade).", str(ctx.exception))

    # 9. Ausência de App ID
    def test_ausencia_app_id(self):
        with self.assertRaises(ValueError) as ctx1:
            self.client.listar_contas(self.mock_pat, "")
        self.assertIn("DERIV_APP_ID não configurado", str(ctx1.exception))

        with self.assertRaises(ValueError) as ctx2:
            self.client.solicitar_otp(self.mock_pat, None, "DOT123456")
        self.assertIn("DERIV_APP_ID não configurado", str(ctx2.exception))

    # 10. Múltiplas contas do mesmo tipo
    def test_multiplas_contas(self):
        contas = [
            {"account_id": "DOT111", "account_type": "demo", "status": "disabled", "balance": 10.0},
            {"account_id": "DOT222", "account_type": "demo", "status": "active", "balance": 5000.0},
            {"account_id": "DOT333", "account_type": "demo", "status": "active", "balance": 10000.0},
            {"account_id": "ROT888", "account_type": "real", "status": "active", "balance": 50.0},
            {"account_id": "ROT999", "account_type": "real", "status": "active", "balance": 200.0},
        ]
        # Padrão seleciona demo ativa
        conta_demo = self.client.selecionar_conta_padrao(contas, preferir_real=False)
        self.assertEqual(conta_demo["account_type"], "demo")
        self.assertEqual(conta_demo["status"], "active")

        # Seleção por account_id específico
        conta_especifica = self.client.selecionar_conta_padrao(contas, account_id_especifico="ROT999")
        self.assertEqual(conta_especifica["account_id"], "ROT999")
        self.assertEqual(conta_especifica["balance"], 200.0)

        # ID inexistente lança DerivAccountNotFoundError
        with self.assertRaises(DerivAccountNotFoundError):
            self.client.selecionar_conta_padrao(contas, account_id_especifico="INEXISTENTE_999")

    # 11. Token / OTP nunca aparece nos logs
    def test_token_nunca_aparece_nos_logs(self):
        url_com_otp = "wss://ws.derivws.com/websockets/v3?app_id=12345&otp=super_secret_otp_token_abcd"
        url_sanitizada = sanitizar_url_ws(url_com_otp)

        self.assertNotIn("super_secret_otp_token_abcd", url_sanitizada)
        self.assertIn("otp=[PROTEGIDO]", url_sanitizada)

        # Com outro formato de query param
        url2 = "wss://example.com/ws?otp=my_secret_token"
        self.assertEqual(sanitizar_url_ws(url2), "wss://example.com/ws?otp=[PROTEGIDO]")


if __name__ == "__main__":
    unittest.main()
