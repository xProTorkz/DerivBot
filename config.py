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

# --------------------------- CONFIGURAÇÕES DE IA ---------------------------
# Configurações para a API DeepSeek e comportamento da IA
IA_CONFIG = {
    "temperature": float(os.getenv("IA_TEMPERATURE", "0.1")),
    "max_tokens": int(os.getenv("IA_MAX_TOKENS", "5")),
    "async_mode": os.getenv("IA_ASYNC_MODE", "False").lower() == "true",
    "timeout": float(os.getenv("IA_TIMEOUT", "2.5")),
    "min_confianca": float(
        os.getenv("IA_MIN_CONFIANCA", "0.6")
    ),  # Mínima confiança para aceitar decisão
    "max_aguardar_consecutivo": int(
        os.getenv("IA_MAX_AGUARDAR", "5")
    ),  # Máximo de decisões AGUARDAR consecutivas
}

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
    "win_rate": 90,  # taxa de acerto estimada para este modo (%)
}

MODO_CONSERVADOR = {
    "max_operacoes": 3,
    "percent_entrada": 0.01,  # 1% do valor da meta
    "stop_consecutivos": 3,  # parar após 3 perdas consecutivas
    "stop_percent": 0.5,  # 50% da meta (stop loss)
    "martingale": 1,  # apenas 1 martingale
    "win_rate": 80,  # taxa de acerto estimada para este modo (%)
}

MODO_AGRESSIVO = {
    "max_operacoes": 5,
    "percent_entrada": 0.05,  # 5% do valor da meta
    "stop_consecutivos": 3,  # parar após 3 perdas consecutivas
    "stop_percent": 0.5,  # 50% da meta (stop loss)
    "martingale": 1,  # apenas 1 martingale
    "win_rate": 75,  # taxa de acerto estimada para este modo (%)
}

# Configurações gerais do micro scalping
MICRO_SCALPING = {
    "suporte_resistencia_janela": 5,  # janela para detectar suporte/resistência
    "suporte_resistencia_margem": 0.03,  # margem para considerar que está no suporte/resistência (3%)
    "rsi_sobrecompra": 70,  # limiar de sobrecompra do RSI
    "rsi_sobrevenda": 30,  # limiar de sobrevenda do RSI
    "meta_minima": 10.0,  # meta mínima em dólares
    "meta_progresso_reducao": 75.0,  # % de progresso da meta para começar a reduzir operações
    "duracao_operacao": 1,  # Tempo para manter a operação aberta (em segundos)
    "multiplier_padrao": 1,  # Multiplicador padrão para contratos multiplier
    "ativo_padrao": "R_10",  # Ativo padrão para micro scalping (aceita operações de 1s)
}

# Configurações de contratos multipliers
MULTIPLIER = {
    "valor": 1,  # Multiplicador padrão (1x é o mais conservador)
    "take_profit": 100,  # Porcentagem de lucro para fechar automaticamente (não usado no micro scalping de 1s)
    "stop_loss": 90,  # Porcentagem de perda para fechar automaticamente (não usado no micro scalping de 1s)
}

# --------------------------- INDICADORES ---------------------------
RSI_PERIODO: int = int(os.getenv("RSI_PERIODO", "5"))
RSI_SOBRECOMPRADO: int = int(os.getenv("RSI_SOBRECOMPRADO", "70"))
RSI_SOBREVENDIDO: int = int(os.getenv("RSI_SOBREVENDIDO", "30"))
BOLLINGER_PERIODO: int = int(os.getenv("BOLLINGER_PERIODO", "10"))
BOLLINGER_DESVIO: int = int(os.getenv("BOLLINGER_DESVIO", "2"))

# --------------------------- LISTA DE ATIVOS ---------------------------
# Atualizado para incluir apenas ativos que aceitam operações de 1 segundo
PARES = [
    "R_10",  # Volatility 10 Index
    "R_25",  # Volatility 25 Index
    "R_50",  # Volatility 50 Index
    "R_75",  # Volatility 75 Index
    "R_100",  # Volatility 100 Index
    "BOOM500",  # Boom 500 Index
    "BOOM1000",  # Boom 1000 Index
    "CRASH500",  # Crash 500 Index
    "CRASH1000",  # Crash 1000 Index
]
PAR_PADRAO = os.getenv("PAR_PADRAO", "R_10")

# --------------------------- CONFIGURAÇÕES DE ARMAZENAMENTO E LIMPEZA ---------------------------
# Configurações para gerenciamento de memória e limpeza de dados
ARMAZENAMENTO = {
    "max_duracao_velas": 6 * 60 * 60,  # Manter velas por 6 horas (em segundos)
    "max_duracao_ticks": 1 * 60 * 60,  # Manter ticks brutos por 1 hora (em segundos)
    "intervalo_limpeza": 30 * 60,  # Verificar limpeza a cada 30 minutos
    "max_velas": 1000,  # Número máximo de velas a armazenar (mesmo sem expirar)
    "max_ticks": 1000,  # Número máximo de ticks a armazenar (mesmo sem expirar)
}

# --------------------------- RECONEXÃO ---------------------------
# Configurações para gerenciamento de conexão e reconexão
CONEXAO = {
    "timeout_inatividade": 15,  # Segundos sem mensagem antes de tentar reconectar
    "max_tentativas_reconexao": 5,  # Número máximo de tentativas de reconexão
    "intervalo_tentativas_base": 2,  # Intervalo base entre tentativas (segundos)
    "intervalo_verificacao": 5,  # Intervalo para verificar status da conexão
}

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
    "ARMAZENAMENTO",
    "CONEXAO",
    "LOG_LEVEL",
    "LOG_FILE",
    "IA_CONFIG",
    "MODO_INICIANTE",
    "MODO_CONSERVADOR",
    "MODO_AGRESSIVO",
    "MICRO_SCALPING",
    "MULTIPLIER",
]
