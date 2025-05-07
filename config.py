"""
Arquivo de configuração para o sistema de scalping.
Contém todas as constantes, chaves de API e configurações do sistema.
"""

# Configurações da API
API_ID = 71203
API_USER_DATA = {
    "lucas-110425-0938-7c3018": {
        "usada": False,
        "email": "pglucas7@gmail.com",
        "token": "0hfU9DKnc0LnCZL",
        "deriv_account": "",
        "ips": ["127.0.0.1"],
        "hwids": ["0x22334d051b1a"],
        "ativado_em": "",
        "token_demo": "RYMx6qlHahIlC53",
        "deriv_demo": "VRTC13064068",
        "ativado_em_demo": "2025-04-11 09:39",
        "token_real": "afK88ZEXLzGdzD9",
        "deriv_real": "CR8745847",
        "ativado_em_real": "2025-04-11 09:39",
    }
}

# Token de acesso atual (usar o demo por padrão para segurança)
ACTIVE_TOKEN = API_USER_DATA["lucas-110425-0938-7c3018"]["token_demo"]

# Configurações de trading
MODO_REAL = False  # False = modo demo, True = modo real
VALOR_ENTRADA = 5  # Valor padrão de entrada em dólares
TIMEFRAME = 1  # Tempo em segundos para cada operação (scalping)
MAX_OPERATIONS = 50  # Número máximo de operações por sessão
STOP_LOSS = 30  # Stop loss em dólares
TAKE_PROFIT = 50  # Take profit em dólares

# Configurações de indicadores para scalping
RSI_PERIODO = 5  # Período curto para RSI, ideal para scalping
RSI_SOBRECOMPRADO = 70
RSI_SOBREVENDIDO = 30
BOLLINGER_PERIODO = 10
BOLLINGER_DESVIO = 2

# Pares de moedas disponíveis
PARES = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
PAR_PADRAO = "EURUSD"

# Configurações de log
LOG_LEVEL = "INFO"
LOG_FILE = "scalping_log.txt"
