#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gerador de Licenças para DerivBot
---------------------------------
Este script gera e gerencia licenças para o DerivBot com diferentes planos:
- FREE: Acesso limitado por 7 dias
- MENSAL: Acesso por 30 dias
- VITALÍCIO: Acesso permanente

Uso:
    python gerador_licencas.py criar -e email@exemplo.com -p vitalicio
    python gerador_licencas.py listar
    python gerador_licencas.py revogar -c CODIGO_LICENCA
    python gerador_licencas.py atualizar -c CODIGO_LICENCA -p mensal
"""

import os
import sys
import json
import uuid
import string
import random
import argparse
from datetime import datetime, timedelta
import hashlib
import hmac
import base64
import time
from typing import Dict, Optional, Tuple, List, Any
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("derivbot.log"), logging.StreamHandler()],
)
logger = logging.getLogger("DerivBot")

# Configurações
LICENCAS_FILE = "data/licencas.json"
PLANOS = {
    "free": {"dias_validade": 7, "limite_operacoes": 100},
    "mensal": {"dias_validade": 30, "limite_operacoes": 1000},
    "vitalicio": {
        "dias_validade": None,  # Sem validade
        "limite_operacoes": None,  # Sem limite
    },
}


def gerar_codigo_licenca(tamanho=15):
    """Gera um código de licença alfanumérico aleatório."""
    caracteres = string.ascii_letters + string.digits
    return "".join(random.choice(caracteres) for _ in range(tamanho))


def gerar_id_licenca(email, nome=None):
    """Gera um ID único para a licença baseado no email, timestamp e um UUID parcial."""
    agora = datetime.now()
    data_formatada = agora.strftime("%y%m%d-%H%M")
    nome_parte = nome.lower().replace(" ", "-") if nome else email.split("@")[0].lower()
    uuid_parte = str(uuid.uuid4())[:6]
    return f"{nome_parte}-{data_formatada}-{uuid_parte}"


def calcular_data_validade(plano):
    """Calcula a data de validade baseada no plano."""
    if plano == "vitalicio":
        return "VITALÍCIO"

    dias = PLANOS[plano]["dias_validade"]
    data_validade = datetime.now() + timedelta(days=dias)
    return data_validade.strftime("%Y-%m-%d")


def carregar_licencas():
    """Carrega o arquivo de licenças ou cria um novo se não existir."""
    if not os.path.exists("data"):
        os.makedirs("data")

    if not os.path.exists(LICENCAS_FILE):
        try:
            with open(LICENCAS_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2, ensure_ascii=False)
            logger.info("Arquivo de licenças criado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao criar arquivo de licenças: {e}")
            return {}

    try:
        with open(LICENCAS_FILE, "r", encoding="utf-8") as f:
            licencas = json.load(f)
            logger.info(
                f"Licenças carregadas: {json.dumps(licencas, indent=2, ensure_ascii=False)}"
            )
            return licencas
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar JSON: {e}")
        # Tenta fazer backup do arquivo corrompido
        try:
            backup_file = f"{LICENCAS_FILE}.bak"
            os.rename(LICENCAS_FILE, backup_file)
            logger.info(f"Backup do arquivo corrompido criado em: {backup_file}")
        except Exception as backup_error:
            logger.error(f"Erro ao criar backup: {backup_error}")
        return {}
    except Exception as e:
        logger.error(f"Erro ao carregar licenças: {e}")
        return {}


def salvar_licencas(licencas):
    """Salva as licenças no arquivo."""
    try:
        with open(LICENCAS_FILE, "w", encoding="utf-8") as f:
            json.dump(licencas, f, indent=2, ensure_ascii=False)
        logger.info(
            f"Licenças salvas com sucesso: {json.dumps(licencas, indent=2, ensure_ascii=False)}"
        )
    except Exception as e:
        logger.error(f"Erro ao salvar licenças: {e}")


def criar_licenca(email, plano, nome=None):
    """Cria uma nova licença com o plano especificado."""
    if plano not in PLANOS:
        return {"erro": f"Plano inválido. Escolha entre: {', '.join(PLANOS.keys())}"}

    licencas = carregar_licencas()

    # Verifica se o email já possui licença
    for lic in licencas.values():
        if lic.get("email") == email and lic.get("status") in ["ativa", "gerada"]:
            return {"erro": f"O email {email} já possui uma licença ativa ou gerada."}

    # Gera um novo ID e código de licença
    id_licenca = gerar_id_licenca(email, nome)
    codigo_licenca = gerar_codigo_licenca()

    # Calcula a data de validade
    validade = calcular_data_validade(plano)

    # Cria o registro da licença
    licencas[id_licenca] = {
        "codigo_licenca": codigo_licenca,
        "email": email,
        "nome": nome,
        "plano": plano,
        "validade": validade,
        "ativado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ips": [],
        "hwids": [],
        "status": "gerada",
        "limite_operacoes": PLANOS[plano]["limite_operacoes"],
    }

    salvar_licencas(licencas)

    return {
        "sucesso": True,
        "id_licenca": id_licenca,
        "codigo_licenca": codigo_licenca,
        "email": email,
        "plano": plano,
        "validade": validade,
    }


def listar_licencas(filtro=None):
    """Lista todas as licenças ou filtra por status/plano."""
    licencas = carregar_licencas()

    if not licencas:
        return {"mensagem": "Nenhuma licença encontrada."}

    resultados = licencas

    if filtro and filtro in ["ativa", "revogada", "expirada"]:
        resultados = {k: v for k, v in licencas.items() if v.get("status") == filtro}

    return {"licencas": resultados}


def revogar_licenca(codigo_licenca):
    """Revoga uma licença específica."""
    licencas = carregar_licencas()

    for id_licenca, licenca in licencas.items():
        if licenca.get("codigo_licenca") == codigo_licenca:
            licenca["status"] = "revogada"
            licenca["revogada_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            salvar_licencas(licencas)
            return {
                "sucesso": True,
                "mensagem": f"Licença {codigo_licenca} revogada com sucesso.",
            }

    return {"erro": f"Licença com código {codigo_licenca} não encontrada."}


def atualizar_licenca(codigo_licenca, plano=None, validade=None):
    """Atualiza uma licença existente."""
    if plano and plano not in PLANOS:
        return {"erro": f"Plano inválido. Escolha entre: {', '.join(PLANOS.keys())}"}

    licencas = carregar_licencas()

    for id_licenca, licenca in licencas.items():
        if licenca.get("codigo_licenca") == codigo_licenca:
            if plano:
                licenca["plano"] = plano
                licenca["limite_operacoes"] = PLANOS[plano]["limite_operacoes"]
                # Atualiza validade se mudar para um plano não vitalício
                if plano != "vitalicio":
                    licenca["validade"] = calcular_data_validade(plano)
                else:
                    licenca["validade"] = "VITALÍCIO"

            if validade:
                licenca["validade"] = validade

            salvar_licencas(licencas)
            return {
                "sucesso": True,
                "mensagem": f"Licença {codigo_licenca} atualizada com sucesso.",
            }

    return {"erro": f"Licença com código {codigo_licenca} não encontrada."}


def verificar_licencas_expiradas():
    """Verifica e marca licenças expiradas."""
    licencas = carregar_licencas()
    hoje = datetime.now().strftime("%Y-%m-%d")

    alteracoes = False
    for id_licenca, licenca in licencas.items():
        if (
            licenca.get("status") == "ativa"
            and licenca.get("validade") != "VITALÍCIO"
            and licenca.get("validade")
            and licenca.get("validade") < hoje
        ):
            licenca["status"] = "expirada"
            alteracoes = True

    if alteracoes:
        salvar_licencas(licencas)

    return {"mensagem": "Verificação de licenças expiradas concluída."}


def processar_argumentos():
    """Processa os argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description="Gerador e Gerenciador de Licenças para DerivBot"
    )
    subparsers = parser.add_subparsers(dest="comando", help="Comandos disponíveis")

    # Comando Criar
    criar_parser = subparsers.add_parser("criar", help="Criar uma nova licença")
    criar_parser.add_argument("-e", "--email", required=True, help="Email do usuário")
    criar_parser.add_argument(
        "-p",
        "--plano",
        required=True,
        choices=PLANOS.keys(),
        help="Plano da licença (free, mensal, vitalicio)",
    )
    criar_parser.add_argument("-n", "--nome", help="Nome do usuário (opcional)")

    # Comando Listar
    listar_parser = subparsers.add_parser("listar", help="Listar licenças")
    listar_parser.add_argument(
        "-f",
        "--filtro",
        choices=["ativa", "revogada", "expirada"],
        help="Filtrar por status",
    )

    # Comando Revogar
    revogar_parser = subparsers.add_parser("revogar", help="Revogar uma licença")
    revogar_parser.add_argument(
        "-c", "--codigo", required=True, help="Código da licença"
    )

    # Comando Atualizar
    atualizar_parser = subparsers.add_parser("atualizar", help="Atualizar uma licença")
    atualizar_parser.add_argument(
        "-c", "--codigo", required=True, help="Código da licença"
    )
    atualizar_parser.add_argument(
        "-p", "--plano", choices=PLANOS.keys(), help="Novo plano da licença"
    )
    atualizar_parser.add_argument(
        "-v", "--validade", help="Nova data de validade (formato: YYYY-MM-DD)"
    )

    # Comando Verificar
    subparsers.add_parser("verificar", help="Verificar licenças expiradas")

    args = parser.parse_args()

    if not args.comando:
        parser.print_help()
        sys.exit(1)

    return args


def main():
    """Função principal do programa."""
    args = processar_argumentos()

    if args.comando == "criar":
        resultado = criar_licenca(args.email, args.plano, args.nome)
        if "erro" in resultado:
            print(f"ERRO: {resultado['erro']}")
        else:
            print(f"✅ Licença criada com sucesso!")
            print(f"ID: {resultado['id_licenca']}")
            print(f"Código: {resultado['codigo_licenca']}")
            print(f"Email: {resultado['email']}")
            print(f"Plano: {resultado['plano'].upper()}")
            print(f"Validade: {resultado['validade']}")

    elif args.comando == "listar":
        resultado = listar_licencas(args.filtro)
        if "mensagem" in resultado:
            print(resultado["mensagem"])
        else:
            print(f"Total de licenças: {len(resultado['licencas'])}")
            print("\nLicenças:")
            for id_licenca, licenca in resultado["licencas"].items():
                status_emoji = "✅" if licenca.get("status") == "ativa" else "❌"
                print(f"\n{status_emoji} {id_licenca}:")
                print(f"  Código: {licenca.get('codigo_licenca')}")
                print(f"  Email: {licenca.get('email')}")
                print(f"  Plano: {licenca.get('plano', 'N/A').upper()}")
                print(f"  Validade: {licenca.get('validade', 'N/A')}")
                print(f"  Status: {licenca.get('status', 'N/A')}")

    elif args.comando == "revogar":
        resultado = revogar_licenca(args.codigo)
        if "erro" in resultado:
            print(f"ERRO: {resultado['erro']}")
        else:
            print(resultado["mensagem"])

    elif args.comando == "atualizar":
        if not args.plano and not args.validade:
            print(
                "ERRO: Você deve especificar pelo menos um parâmetro para atualizar (plano ou validade)."
            )
        else:
            resultado = atualizar_licenca(args.codigo, args.plano, args.validade)
            if "erro" in resultado:
                print(f"ERRO: {resultado['erro']}")
            else:
                print(resultado["mensagem"])

    elif args.comando == "verificar":
        resultado = verificar_licencas_expiradas()
        print(resultado["mensagem"])


class LicencaManager:
    def __init__(self):
        self.logger = logging.getLogger("LicencaManager")
        self.data_dir = "data"
        self.licencas_file = os.path.join(self.data_dir, "licencas.json")

        # Cria diretório se não existir
        os.makedirs(self.data_dir, exist_ok=True)

        # Configuração de criptografia
        self._setup_encryption()

        # Carrega licenças
        self.licencas = self._carregar_licencas()

    def _setup_encryption(self):
        """Configura sistema de criptografia"""
        try:
            # Gera chave mestra
            salt = b"derivbot_salt"  # Em produção, usar salt aleatório
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(b"derivbot_master_key"))

            # Inicializa Fernet
            self.cipher = Fernet(key)

        except Exception as e:
            self.logger.error(f"Erro ao configurar criptografia: {str(e)}")
            raise

    def _carregar_licencas(self) -> Dict[str, Dict]:
        """Carrega licenças do arquivo"""
        try:
            if os.path.exists(self.licencas_file):
                with open(self.licencas_file, "r") as f:
                    dados = json.load(f)

                # Decripta licenças
                licencas = {}
                for email, licenca in dados.items():
                    try:
                        licenca_decrypt = self._decrypt_licenca(licenca)
                        licencas[email] = licenca_decrypt
                    except:
                        self.logger.warning(f"Licença inválida para {email}")

                return licencas
            return {}

        except Exception as e:
            self.logger.error(f"Erro ao carregar licenças: {str(e)}")
            return {}

    def _salvar_licencas(self):
        """Salva licenças no arquivo"""
        try:
            # Criptografa licenças
            dados = {}
            for email, licenca in self.licencas.items():
                dados[email] = self._encrypt_licenca(licenca)

            with open(self.licencas_file, "w") as f:
                json.dump(dados, f, indent=4)

        except Exception as e:
            self.logger.error(f"Erro ao salvar licenças: {str(e)}")

    def _encrypt_licenca(self, licenca: Dict) -> str:
        """Criptografa dados da licença"""
        try:
            dados = json.dumps(licenca)
            return self.cipher.encrypt(dados.encode()).decode()

        except Exception as e:
            self.logger.error(f"Erro ao criptografar licença: {str(e)}")
            raise

    def _decrypt_licenca(self, licenca_encrypt: str) -> Dict:
        """Decriptografa dados da licença"""
        try:
            dados = self.cipher.decrypt(licenca_encrypt.encode())
            return json.loads(dados)

        except Exception as e:
            self.logger.error(f"Erro ao decriptografar licença: {str(e)}")
            raise

    def gerar_licenca(
        self, email: str, duracao_dias: int = 30, admin: bool = False
    ) -> Optional[Dict]:
        """Gera nova licença"""
        try:
            # Gera token único
            token = self._gerar_token(email)

            # Define datas
            agora = datetime.now()
            expiracao = agora + timedelta(days=duracao_dias)

            # Cria licença
            licenca = {
                "email": email,
                "token": token,
                "criacao": agora.isoformat(),
                "expiracao": expiracao.isoformat(),
                "admin": admin,
                "ativa": True,
            }

            # Adiciona hash de verificação
            licenca["hash"] = self._gerar_hash(licenca)

            # Salva licença
            self.licencas[email] = licenca
            self._salvar_licencas()

            return licenca

        except Exception as e:
            self.logger.error(f"Erro ao gerar licença: {str(e)}")
            return None

    def _gerar_token(self, email: str) -> str:
        """Gera token único para licença"""
        try:
            # Combina email, timestamp e salt
            dados = f"{email}:{time.time()}:derivbot_salt"

            # Gera hash
            token = hashlib.sha256(dados.encode()).hexdigest()

            return token

        except Exception as e:
            self.logger.error(f"Erro ao gerar token: {str(e)}")
            raise

    def _gerar_hash(self, licenca: Dict) -> str:
        """Gera hash de verificação para licença"""
        try:
            # Remove hash existente se houver
            dados = licenca.copy()
            dados.pop("hash", None)

            # Converte para string
            dados_str = json.dumps(dados, sort_keys=True)

            # Gera hash
            return hmac.new(
                b"derivbot_hash_key", dados_str.encode(), hashlib.sha256
            ).hexdigest()

        except Exception as e:
            self.logger.error(f"Erro ao gerar hash: {str(e)}")
            raise

    def validar_licenca(self, email: str, token: str) -> bool:
        """Valida licença"""
        try:
            # Verifica se licença existe
            if email not in self.licencas:
                return False

            licenca = self.licencas[email]

            # Verifica se está ativa
            if not licenca["ativa"]:
                return False

            # Verifica token
            if licenca["token"] != token:
                return False

            # Verifica expiração
            expiracao = datetime.fromisoformat(licenca["expiracao"])
            if datetime.now() > expiracao:
                return False

            # Verifica hash
            hash_atual = self._gerar_hash(licenca)
            if hash_atual != licenca["hash"]:
                return False

            return True

        except Exception as e:
            self.logger.error(f"Erro ao validar licença: {str(e)}")
            return False

    def validar_login(self, email: str, token: str) -> bool:
        """Valida login do usuário"""
        return self.validar_licenca(email, token)

    def is_admin(self, email: str) -> bool:
        """Verifica se usuário é admin"""
        try:
            if email not in self.licencas:
                return False

            return self.licencas[email]["admin"]

        except Exception as e:
            self.logger.error(f"Erro ao verificar admin: {str(e)}")
            return False

    def revogar_licenca(self, email: str) -> bool:
        """Revoga licença"""
        try:
            if email not in self.licencas:
                return False

            # Marca como inativa
            self.licencas[email]["ativa"] = False

            # Salva alterações
            self._salvar_licencas()

            return True

        except Exception as e:
            self.logger.error(f"Erro ao revogar licença: {str(e)}")
            return False

    def listar_licencas(self) -> List[Dict]:
        """Lista todas as licenças"""
        try:
            # Remove informações sensíveis
            licencas = []
            for licenca in self.licencas.values():
                licenca_copy = licenca.copy()
                licenca_copy.pop("token", None)
                licenca_copy.pop("hash", None)
                licencas.append(licenca_copy)

            return licencas

        except Exception as e:
            self.logger.error(f"Erro ao listar licenças: {str(e)}")
            return []


# Instância global do gerenciador de licenças
# licenca_manager = LicencaManager()  # Desabilitado para usar sistema simples


def obter_hwid():
    """Obtém o HWID do dispositivo atual"""
    try:
        import wmi
        import pythoncom

        # Inicializa COM para a thread atual
        pythoncom.CoInitialize()

        c = wmi.WMI()
        for item in c.Win32_ComputerSystemProduct():
            hwid = f"0x{item.UUID.replace('-', '')[:12]}"
            logger.info(f"HWID obtido: {hwid}")
            return hwid
    except ImportError:
        logger.error("Módulo WMI não encontrado. Instale com: pip install wmi")
        return None
    except Exception as e:
        logger.error(f"Erro ao obter HWID: {e}")
        return None
    finally:
        try:
            pythoncom.CoUninitialize()
        except:
            pass


def obter_ip():
    """Obtém o IP público da rede"""
    try:
        import requests

        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        if response.status_code == 200:
            ip = response.json()["ip"]
            logger.info(f"IP obtido: {ip}")
            return ip
        logger.error(f"Erro ao obter IP: Status {response.status_code}")
        return None
    except ImportError:
        logger.error(
            "Módulo requests não encontrado. Instale com: pip install requests"
        )
        return None
    except Exception as e:
        logger.error(f"Erro ao obter IP: {e}")
        return None


def validar_dispositivo(licenca, hwid=None, ip=None):
    """
    Valida se o dispositivo atual está autorizado para a licença
    Retorna True se for primeiro acesso ou se pelo menos 1 dos 3 métodos (HWID, IP, Token) conferir
    """
    if not hwid:
        hwid = obter_hwid()
    if not ip:
        ip = obter_ip()

    logger.info(f"Validando dispositivo - HWID: {hwid}, IP: {ip}")

    # Se é primeiro acesso (nenhum dispositivo vinculado), permite
    if not licenca.get("hwid") and not licenca.get("ip"):
        logger.info("Primeiro acesso - Permitindo")
        return True

    # Conta quantos métodos conferem
    metodos_conferidos = 0

    # Verifica HWID
    if hwid and hwid == licenca.get("hwid"):
        metodos_conferidos += 1
        logger.info("HWID válido")

    # Verifica IP
    if ip and ip == licenca.get("ip"):
        metodos_conferidos += 1
        logger.info("IP válido")

    # Verifica Token
    if licenca.get("token_deriv_real"):
        metodos_conferidos += 1
        logger.info("Token válido")

    logger.info(f"Total de métodos conferidos: {metodos_conferidos}")

    # Se nenhum método está configurado, permite o acesso
    if not licenca.get("hwid") and not licenca.get("ip"):
        logger.info("Nenhum dispositivo vinculado - Permitindo")
        return True

    # Retorna True se pelo menos 1 método conferir
    return metodos_conferidos >= 1


def vincular_dispositivo(licenca, hwid=None, ip=None):
    """
    Vincula o dispositivo atual à licença
    """
    if not hwid:
        hwid = obter_hwid()
    if not ip:
        ip = obter_ip()

    logger.info(f"Vinculando dispositivo - HWID: {hwid}, IP: {ip}")

    # Vincula HWID (apenas um por licença)
    if hwid:
        licenca["hwid"] = hwid
        logger.info(f"HWID vinculado: {hwid}")

    # Vincula IP (apenas um por licença)
    if ip:
        licenca["ip"] = ip
        logger.info(f"IP vinculado: {ip}")

    # Carrega todas as licenças
    licencas = carregar_licencas()

    # Atualiza a licença específica
    for id_licenca, l in licencas.items():
        if l.get("codigo_licenca") == licenca.get("codigo_licenca"):
            licencas[id_licenca] = licenca
            break

    # Salva as alterações
    salvar_licencas(licencas)
    logger.info("Dispositivo vinculado com sucesso")

    return licenca


if __name__ == "__main__":
    main()
