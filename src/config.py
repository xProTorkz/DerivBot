import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Configurações do Flask
FLASK_CONFIG = {
    "SECRET_KEY": os.getenv("FLASK_SECRET_KEY", "chave-secreta-padrao"),
    "DEBUG": os.getenv("FLASK_DEBUG", "True").lower() == "true",
    "HOST": os.getenv("FLASK_HOST", "0.0.0.0"),
    "PORT": int(os.getenv("FLASK_PORT", "5000")),
}

# Configurações da API Deriv
DERIV_CONFIG = {
    "API_KEY": os.getenv("DERIV_API_KEY", ""),
    "APP_ID": os.getenv("DERIV_APP_ID", ""),
    "WEBSOCKET_URL": os.getenv(
        "DERIV_WEBSOCKET_URL", "wss://ws.binaryws.com/websockets/v3"
    ),
}

# Configurações do Bot
BOT_CONFIG = {
    "MODO_INICIANTE": {
        "valor_inicial": 2.0,
        "martingale": 2.0,
        "max_operacoes": 3,
        "min_confianca": 0.7,
    },
    "MODO_INTERMEDIARIO": {
        "valor_inicial": 5.0,
        "martingale": 2.0,
        "max_operacoes": 5,
        "min_confianca": 0.8,
    },
    "MODO_AVANCADO": {
        "valor_inicial": 10.0,
        "martingale": 2.0,
        "max_operacoes": 10,
        "min_confianca": 0.9,
    },
}

# Configurações de Log
LOG_CONFIG = {
    "level": os.getenv("LOG_LEVEL", "INFO"),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": os.getenv("LOG_FILE", "trading.log"),
}

# Configurações de Diretórios
DIRS = {
    "data": os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"),
    "logs": os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs"),
    "templates": os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"),
    "static": os.path.join(os.path.dirname(os.path.dirname(__file__)), "static"),
}

# Cria diretórios se não existirem
for dir_path in DIRS.values():
    os.makedirs(dir_path, exist_ok=True)

# Configurações de Trading
PAR_PADRAO = "R_10"  # Par padrão para operações
PARES = ["R_10", "R_25", "R_50", "R_75", "R_100"]  # Pares disponíveis

# Configurações de IA
IA_CONFIG = {
    "async_mode": False,
    "timeout": 2.5,
    "temperature": 0.1,
    "max_tokens": 5,
    "max_aguardar_consecutivo": 5,
}
