"""
Arquivo de configuração para o sistema de scalping.
Contém todas as constantes, chaves de API e configurações do sistema.
"""

from __future__ import annotations
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env (na raiz do projeto)
load_dotenv()

# --------------------------- VARIÁVEIS SENSÍVEIS ---------------------------
# Estes dados devem ficar apenas no .env. Caso uma variável não exista no .env
# será utilizado o valor default informado entre aspas.
API_ID: int = int(os.getenv("API_ID", "71203"))  # Seu app_id cadastrado na Deriv
ACTIVE_TOKEN: str = os.getenv(
    "ACTIVE_TOKEN", ""
)  # Token demo ou real para testes locais

# --------------------------- CONFIGURAÇÕES DE TRADING ---------------------------
MODO_REAL: bool = os.getenv("MODO_REAL", "False").lower() == "true"
VALOR_ENTRADA: float = float(os.getenv("VALOR_ENTRADA", "5"))
TIMEFRAME: int = int(os.getenv("TIMEFRAME", "1"))  # segundos
MAX_OPERATIONS: int = int(os.getenv("MAX_OPERATIONS", "50"))
STOP_LOSS: float = float(os.getenv("STOP_LOSS", "30"))
TAKE_PROFIT: float = float(os.getenv("TAKE_PROFIT", "50"))

# --------------------------- INDICADORES ---------------------------
RSI_PERIODO: int = int(os.getenv("RSI_PERIODO", "5"))
RSI_SOBRECOMPRADO: int = int(os.getenv("RSI_SOBRECOMPRADO", "70"))
RSI_SOBREVENDIDO: int = int(os.getenv("RSI_SOBREVENDIDO", "30"))
BOLLINGER_PERIODO: int = int(os.getenv("BOLLINGER_PERIODO", "10"))
BOLLINGER_DESVIO: int = int(os.getenv("BOLLINGER_DESVIO", "2"))

# --------------------------- LISTA DE ATIVOS ---------------------------
PARES = [
    "frxEURUSD",
    "frxGBPUSD",
    "frxUSDJPY",
    "frxAUDUSD",
]
PAR_PADRAO = os.getenv("PAR_PADRAO", "frxEURUSD")

# --------------------------- LOG ---------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "scalping_log.txt")

__all__ = [
    "API_ID",
    "ACTIVE_TOKEN",
    "MODO_REAL",
    "VALOR_ENTRADA",
    "TIMEFRAME",
    "MAX_OPERATIONS",
    "STOP_LOSS",
    "TAKE_PROFIT",
    "RSI_PERIODO",
    "RSI_SOBRECOMPRADO",
    "RSI_SOBREVENDIDO",
    "BOLLINGER_PERIODO",
    "BOLLINGER_DESVIO",
    "PARES",
    "PAR_PADRAO",
    "LOG_LEVEL",
    "LOG_FILE",
]
