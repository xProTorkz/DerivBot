"""
Arquivo de configuração para o DerivBot
Contém constantes e configurações globais
"""

import os
import json
import logging
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env na pasta config
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)


class Config:
    # Versão do aplicativo
    VERSION = "2.0.0"

    # Diretórios - ajustado para a nova estrutura
    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    DATA_DIR = os.path.join(BASE_DIR, "data")
    LOGS_DIR = os.path.join(BASE_DIR, "logs")

    # Cria diretórios se não existirem
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    # Configurações de logging
    LOG_CONFIG = {
        "level": "INFO",  # DEBUG, INFO, WARNING, ERROR
        "file": os.path.join(LOGS_DIR, "derivbot.log"),
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "max_size": 10 * 1024 * 1024,  # 10MB
        "backup_count": 5,
        "console_output": True,
        "file_output": True,
    }

    # Configurações da API Deriv
    DERIV_WEBSOCKET_URL = "wss://ws.derivws.com/websockets/v3"
    DERIV_APP_ID = 71203

    # Configurações do servidor Flask
    FLASK_HOST = "0.0.0.0"
    FLASK_PORT = 5000
    FLASK_DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    SECRET_KEY = os.getenv("SECRET_KEY", "derivbot-secret-key-2024-production")

    # Configurações de segurança
    MAX_LOGIN_ATTEMPTS = 5
    SESSION_TIMEOUT = 3600  # segundos
    PASSWORD_MIN_LENGTH = 8

    # Configurações de trading
    MODO_REAL_PADRAO = True  # Sempre inicia em real por padrão
    TIMEFRAME_PADRAO = 1  # segundos
    MAX_OPERACOES_SIMULTANEAS = 10
    ATIVO_PADRAO = "1HZ75V"  # VIX75 para scalping

    # Configurações de indicadores técnicos
    INDICADORES = {
        "RSI": {"periodo": 14, "sobrecomprado": 70, "sobrevendido": 30},
        "BOLLINGER": {"periodo": 20, "desvio": 2},
        "EMA": {"rapida": 8, "lenta": 21},
    }

    # Configurações de email (opcional)
    EMAIL_CONFIG = {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "",  # Configure se necessário
        "smtp_pass": "",  # Configure se necessário
    }

    # API Key do DeepSeek (opcional - configure aqui se necessário)
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

    # Configurações de conexão e reconexão
    CONEXAO = {
        "timeout_inatividade": 15,  # segundos sem resposta para reconectar
        "max_tentativas_reconexao": 5,
        "intervalo_tentativas_base": 2,  # segundos
        "intervalo_verificacao": 5,  # segundos
        "timeout_conexao": 10,  # segundos para timeout de conexão
        "ping_interval": 30,  # segundos entre pings
        "max_reconexoes_por_hora": 10,
    }

    # Configurações de operação
    MODOS_OPERACAO = {
        "iniciante": {
            "entrada_inicial": 1.0,
            "multiplicador": 2.0,
            "max_martingale": 3,
            "meta_maxima": 20.0,
            "operacoes_simultaneas": 3,
            "assertividade": 0.95,
            # Configurações de stops
            "stop_loss_operacao_percent": 1.5,
            "take_profit_operacao_percent": 3.0,
            "stop_loss_global_percent": 5.0,
            "take_profit_global_percent": 10.0,
            "trailing_stop_ativo": False,
            "trailing_stop_distancia": 0.5,
        },
        "conservador": {
            "entrada_inicial": 5.0,
            "multiplicador": 1.5,
            "max_martingale": 2,
            "meta_maxima": 50.0,
            "operacoes_simultaneas": 5,
            "assertividade": 0.85,
            # Configurações de stops
            "stop_loss_operacao_percent": 2.0,
            "take_profit_operacao_percent": 4.0,
            "stop_loss_global_percent": 8.0,
            "take_profit_global_percent": 15.0,
            "trailing_stop_ativo": True,
            "trailing_stop_distancia": 1.0,
        },
        "agressivo": {
            "entrada_inicial": 10.0,
            "multiplicador": 2.5,
            "max_martingale": 4,
            "meta_maxima": 100.0,
            "operacoes_simultaneas": 10,
            "assertividade": 0.80,
            # Configurações de stops
            "stop_loss_operacao_percent": 3.0,
            "take_profit_operacao_percent": 6.0,
            "stop_loss_global_percent": 15.0,
            "take_profit_global_percent": 25.0,
            "trailing_stop_ativo": True,
            "trailing_stop_distancia": 1.0,
        },
    }

    # Configurações de notificação
    NOTIFICACOES_PADRAO = {
        "notificar_fim_operacao": True,
        "notificar_meta_atingida": True,
        "som_ativo": True,
        "desktop_ativo": False,
        "whatsapp_ativo": False,
        "whatsapp_numero": "",
    }

    # Configurações de planos
    PLANOS = {
        "free": {
            "nome": "Gratuito",
            "preco": 0,
            "operacoes_diarias": 10,
            "recursos": ["Acesso básico", "Modo iniciante", "Suporte por e-mail"],
        },
        "mensal": {
            "nome": "Mensal",
            "preco": 49.90,
            "operacoes_diarias": 100,
            "recursos": [
                "Acesso completo",
                "Todos os modos",
                "Suporte prioritário",
                "Notificações",
            ],
        },
        "vitalicio": {
            "nome": "Vitalício",
            "preco": 499.90,
            "operacoes_diarias": "Ilimitadas",
            "recursos": [
                "Acesso completo",
                "Todos os modos",
                "Suporte VIP",
                "Notificações",
                "Atualizações vitalícias",
            ],
        },
    }

    # Configurações de suporte
    SUPORTE_WHATSAPP = "5511999999999"

    # Configurações de validação e tratamento de erros
    VALIDACAO = {
        "timeout_operacao": 30,  # segundos para timeout de operação
        "max_tentativas_reconexao": 5,
        "intervalo_tentativas": 2,  # segundos entre tentativas
        "timeout_resposta_api": 10,  # segundos para timeout de resposta da API
        "max_erros_consecutivos": 3,  # máximo de erros antes de parar
        "intervalo_verificacao_stops": 1,  # segundos entre verificações de stops
        "alertas_preventivos": True,  # ativa alertas antes dos stops
        "percentual_alerta_stop": 80,  # % do stop para disparar alerta (80% = alerta aos 80% do stop)
    }

    # Configurações de logs aprimoradas
    LOG_CONFIG_AVANCADO = {
        "nivel_console": "INFO",  # DEBUG, INFO, WARNING, ERROR
        "nivel_arquivo": "DEBUG",
        "max_logs_memoria": 200,  # logs mantidos em memória
        "max_logs_painel": 50,  # logs exibidos no painel
        "categorias": {
            "sistema": {"cor": "#2196F3", "emoji": "⚙️"},
            "trading": {"cor": "#4CAF50", "emoji": "💹"},
            "stops": {"cor": "#FF9800", "emoji": "🛑"},
            "erro": {"cor": "#F44336", "emoji": "❌"},
            "sucesso": {"cor": "#4CAF50", "emoji": "✅"},
            "alerta": {"cor": "#FF5722", "emoji": "⚠️"},
        },
        "formato_timestamp": "%d/%m/%Y %H:%M:%S",
        "incluir_milissegundos": True,
        "auto_limpeza": True,  # limpa logs antigos automaticamente
        "intervalo_limpeza": 3600,  # segundos (1 hora)
    }

    # Configurações de feedback em tempo real
    FEEDBACK_TEMPO_REAL = {
        "intervalo_atualizacao": 1000,  # milissegundos
        "max_logs_exibidos": 20,
        "auto_scroll": True,
        "notificacoes_visuais": True,
        "sons_alertas": True,
        "cores_status": {
            "conectado": "#4CAF50",
            "desconectado": "#F44336",
            "operando": "#2196F3",
            "pausado": "#FF9800",
            "erro": "#F44336",
        },
        "animacoes": True,
        "fade_logs_antigos": True,
    }

    @staticmethod
    def carregar_tokens():
        """
        Carrega os tokens salvos

        Returns:
            dict: Tokens salvos
        """
        tokens_file = os.path.join(Config.DATA_DIR, "tokens.json")

        if os.path.exists(tokens_file):
            try:
                with open(tokens_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Erro ao carregar tokens: {e}")

        return {"token_real": None, "token_demo": None}

    @staticmethod
    def salvar_tokens(token_real=None, token_demo=None):
        """
        Salva os tokens

        Args:
            token_real: Token da conta real
            token_demo: Token da conta demo

        Returns:
            bool: True se salvou com sucesso, False caso contrário
        """
        tokens = Config.carregar_tokens()

        if token_real:
            tokens["token_real"] = token_real

        if token_demo:
            tokens["token_demo"] = token_demo

        tokens_file = os.path.join(Config.DATA_DIR, "tokens.json")

        try:
            with open(tokens_file, "w") as f:
                json.dump(tokens, f)
            return True
        except Exception as e:
            logging.error(f"Erro ao salvar tokens: {e}")
            return False

    @staticmethod
    def carregar_configuracoes_notificacao():
        """
        Carrega as configurações de notificação

        Returns:
            dict: Configurações de notificação
        """
        config_file = os.path.join(Config.DATA_DIR, "notificacoes.json")

        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Erro ao carregar configurações de notificação: {e}")

        return Config.NOTIFICACOES_PADRAO

    @staticmethod
    def salvar_configuracoes_notificacao(configs):
        """
        Salva as configurações de notificação

        Args:
            configs: Configurações de notificação

        Returns:
            bool: True se salvou com sucesso, False caso contrário
        """
        config_file = os.path.join(Config.DATA_DIR, "notificacoes.json")

        try:
            with open(config_file, "w") as f:
                json.dump(configs, f)
            return True
        except Exception as e:
            logging.error(f"Erro ao salvar configurações de notificação: {e}")
            return False
