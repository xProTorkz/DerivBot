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

# --------------------------- MICRO SCALPING ---------------------------
# Modos de operação (referência para cálculos)
MODO_INICIANTE = {
    "max_operacoes": 1,
    "percent_entrada": 0.005,  # 0.5% do valor da meta
    "stop_consecutivos": 3,  # parar após 3 perdas consecutivas
    "stop_percent": 0.5,  # 50% da meta (stop loss)
    "martingale": 1,  # apenas 1 martingale
    "win_rate": 95,  # taxa de acerto estimada para este modo (%)
}

MODO_CONSERVADOR = {
    "max_operacoes": 3,
    "percent_entrada": 0.01,  # 1% do valor da meta
    "stop_consecutivos": 3,  # parar após 3 perdas consecutivas
    "stop_percent": 0.5,  # 50% da meta (stop loss)
    "martingale": 1,  # apenas 1 martingale
    "win_rate": 85,  # taxa de acerto estimada para este modo (%)
}

MODO_AGRESSIVO = {
    "max_operacoes": 5,
    "percent_entrada": 0.05,  # 5% do valor da meta
    "stop_consecutivos": 3,  # parar após 3 perdas consecutivas
    "stop_percent": 0.5,  # 50% da meta (stop loss)
    "martingale": 1,  # apenas 1 martingale
    "win_rate": 80,  # taxa de acerto estimada para este modo (%)
}

# Configurações gerais do micro scalping
MICRO_SCALPING = {
    "suporte_resistencia_janela": 5,  # janela para detectar suporte/resistência
    "suporte_resistencia_margem": 0.03,  # margem para considerar que está no suporte/resistência (3%)
    "rsi_sobrecompra": 70,  # limiar de sobrecompra do RSI
    "rsi_sobrevenda": 30,  # limiar de sobrevenda do RSI
    "meta_minima": 10.0,  # meta mínima em dólares
    "meta_progresso_reducao": 75.0,  # % de progresso da meta para começar a reduzir operações
}

# --------------------------- INDICADORES ---------------------------
RSI_PERIODO: int = int(os.getenv("RSI_PERIODO", "5"))
RSI_SOBRECOMPRADO: int = int(os.getenv("RSI_SOBRECOMPRADO", "70"))
RSI_SOBREVENDIDO: int = int(os.getenv("RSI_SOBREVENDIDO", "30"))
BOLLINGER_PERIODO: int = int(os.getenv("BOLLINGER_PERIODO", "10"))
BOLLINGER_DESVIO: int = int(os.getenv("BOLLINGER_DESVIO", "2"))

# --------------------------- LISTA DE ATIVOS ---------------------------
PARES = [
    "R_100",  # Volatility 100 Index
    "R_50",  # Volatility 50 Index
    "R_25",  # Volatility 25 Index
    "R_10",  # Volatility 10 Index
]
PAR_PADRAO = os.getenv("PAR_PADRAO", "R_100")

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
