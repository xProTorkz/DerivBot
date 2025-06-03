"""
Arquivo de configuração para o DerivBot
Contém constantes e configurações globais
"""

import os
import json
import logging
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

class Config:
    # Versão do aplicativo
    VERSION = "2.0.0"
    
    # Diretórios - ajustado para a nova estrutura
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    LOGS_DIR = os.path.join(BASE_DIR, "logs")
    
    # Cria diretórios se não existirem
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    # Configurações de logging
    LOG_FILE = os.path.join(LOGS_DIR, "derivbot.log")
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configurações da API
    API_URL = "wss://ws.binaryws.com/websockets/v3"
    
    # Configurações do servidor Flask
    FLASK_HOST = "0.0.0.0"
    FLASK_PORT = 5000
    FLASK_DEBUG = False
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24).hex())
    
    # Configurações de operação
    MODOS_OPERACAO = {
        "iniciante": {
            "entrada_inicial": 1.0,
            "multiplicador": 2.0,
            "max_martingale": 3,
            "stop_win": 10.0,
            "stop_loss": 20.0,
            "assertividade": 0.95
        },
        "conservador": {
            "entrada_inicial": 5.0,
            "multiplicador": 1.5,
            "max_martingale": 2,
            "stop_win": 25.0,
            "stop_loss": 50.0,
            "assertividade": 0.85
        },
        "agressivo": {
            "entrada_inicial": 10.0,
            "multiplicador": 2.5,
            "max_martingale": 4,
            "stop_win": 50.0,
            "stop_loss": 100.0,
            "assertividade": 0.80
        }
    }
    
    # Configurações de notificação
    NOTIFICACOES_PADRAO = {
        "notificar_fim_operacao": True,
        "notificar_meta_atingida": True,
        "som_ativo": True,
        "desktop_ativo": False,
        "whatsapp_ativo": False,
        "whatsapp_numero": ""
    }
    
    # Configurações de planos
    PLANOS = {
        "free": {
            "nome": "Gratuito",
            "preco": 0,
            "operacoes_diarias": 10,
            "recursos": ["Acesso básico", "Modo iniciante", "Suporte por e-mail"]
        },
        "mensal": {
            "nome": "Mensal",
            "preco": 49.90,
            "operacoes_diarias": 100,
            "recursos": ["Acesso completo", "Todos os modos", "Suporte prioritário", "Notificações"]
        },
        "vitalicio": {
            "nome": "Vitalício",
            "preco": 499.90,
            "operacoes_diarias": "Ilimitadas",
            "recursos": ["Acesso completo", "Todos os modos", "Suporte VIP", "Notificações", "Atualizações vitalícias"]
        }
    }
    
    # Configurações de suporte
    SUPORTE_WHATSAPP = "5511999999999"
    
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
                with open(tokens_file, 'r') as f:
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
            with open(tokens_file, 'w') as f:
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
                with open(config_file, 'r') as f:
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
            with open(config_file, 'w') as f:
                json.dump(configs, f)
            return True
        except Exception as e:
            logging.error(f"Erro ao salvar configurações de notificação: {e}")
            return False
