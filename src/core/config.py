"""
Arquivo de configuração para o sistema de scalping.
Contém todas as constantes, chaves de API e configurações do sistema.
"""

from __future__ import annotations
import os
from dotenv import load_dotenv
from typing import Dict, Any
import json
import logging
from datetime import datetime

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
    "max_operacoes": 4,  # Aumentado de 3 para 4 para permitir mais operações simultâneas
    "percent_entrada": 0.01,  # 1% do valor da meta
    "stop_consecutivos": 3,  # parar após 3 perdas consecutivas
    "stop_percent": 0.5,  # 50% da meta (stop loss)
    "martingale": 1,  # apenas 1 martingale
    "win_rate": 80,  # taxa de acerto estimada para este modo (%)
}

MODO_AGRESSIVO = {
    "max_operacoes": 6,  # Aumentado de 5 para 6
    "percent_entrada": 0.06,  # Aumentado de 5% para 6% do valor da meta
    "stop_consecutivos": 4,  # Aumentado de 3 para 4 para maior tolerância
    "stop_percent": 0.6,  # Aumentado de 50% para 60% da meta (stop loss maior)
    "martingale": 2,  # Permitir até 2 martingales
    "win_rate": 70,  # taxa de acerto estimada para este modo (%)
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
    "ativo_padrao": "R_100",  # Ativo padrão para micro scalping (aceita operações de 1s)
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
# Lista completa de ativos que suportam scalping ultra rápido (1-5 segundos)
ATIVOS_SCALPING = {
    # Volatility Indices - Ideais para scalping (24/7, alta volatilidade)
    "R_10": {
        "nome": "Volatility 10 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "baixa",
        "spread": "baixo",
        "horario": "24/7",
        "prioridade": 9,  # Alta prioridade
    },
    "R_25": {
        "nome": "Volatility 25 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "media",
        "spread": "baixo",
        "horario": "24/7",
        "prioridade": 8,
    },
    "R_50": {
        "nome": "Volatility 50 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "media-alta",
        "spread": "baixo",
        "horario": "24/7",
        "prioridade": 7,
    },
    "R_75": {
        "nome": "Volatility 75 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "alta",
        "spread": "baixo",
        "horario": "24/7",
        "prioridade": 6,
    },
    "R_100": {
        "nome": "Volatility 100 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "muito-alta",
        "spread": "baixo",
        "horario": "24/7",
        "prioridade": 8,  # Boa para scalping
    },
    # Jump Indices - Excelentes para scalping rápido
    "JD10": {
        "nome": "Jump 10 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "baixa",
        "spread": "muito-baixo",
        "horario": "24/7",
        "prioridade": 9,
    },
    "JD25": {
        "nome": "Jump 25 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "media",
        "spread": "muito-baixo",
        "horario": "24/7",
        "prioridade": 8,
    },
    "JD50": {
        "nome": "Jump 50 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "media-alta",
        "spread": "muito-baixo",
        "horario": "24/7",
        "prioridade": 7,
    },
    "JD75": {
        "nome": "Jump 75 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "alta",
        "spread": "muito-baixo",
        "horario": "24/7",
        "prioridade": 6,
    },
    "JD100": {
        "nome": "Jump 100 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "muito-alta",
        "spread": "muito-baixo",
        "horario": "24/7",
        "prioridade": 7,
    },
    # Crash/Boom Indices - Bons para scalping em momentos específicos
    "BOOM500": {
        "nome": "Boom 500 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "extrema",
        "spread": "medio",
        "horario": "24/7",
        "prioridade": 5,  # Mais arriscado
    },
    "BOOM1000": {
        "nome": "Boom 1000 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "extrema",
        "spread": "medio",
        "horario": "24/7",
        "prioridade": 4,
    },
    "CRASH500": {
        "nome": "Crash 500 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "extrema",
        "spread": "medio",
        "horario": "24/7",
        "prioridade": 5,
    },
    "CRASH1000": {
        "nome": "Crash 1000 Index",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "extrema",
        "spread": "medio",
        "horario": "24/7",
        "prioridade": 4,
    },
    # Step Indices - Novos ativos para scalping
    "STPUSD": {
        "nome": "Step Index USD",
        "min_stake": 0.35,
        "max_stake": 50000,
        "volatilidade": "controlada",
        "spread": "baixo",
        "horario": "24/7",
        "prioridade": 6,
    },
}

# Lista simplificada para compatibilidade
PARES = list(ATIVOS_SCALPING.keys())
PAR_PADRAO = os.getenv("PAR_PADRAO", "R_100")

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


class Config:
    def __init__(self):
        # Configurações gerais
        self.DEBUG = True
        self.LOG_LEVEL = logging.INFO
        self.DATA_DIR = "data"

        # Configurações de trading
        self.TAKE_PROFIT = 0.02  # 2%
        self.STOP_LOSS = 0.01  # 1%
        self.MAX_OPERATIONS = 5
        self.MIN_BALANCE = 100  # USD

        # Modos de operação
        self.MODO_INICIANTE = {
            "min_confianca": 0.95,
            "max_operacoes": 3,
            "take_profit": 0.02,
            "stop_loss": 0.01,
            "martingale": False,
        }

        self.MODO_INTERMEDIARIO = {
            "min_confianca": 0.85,
            "max_operacoes": 5,
            "take_profit": 0.03,
            "stop_loss": 0.015,
            "martingale": True,
            "martingale_fator": 2,
        }

        self.MODO_AVANCADO = {
            "min_confianca": 0.80,
            "max_operacoes": 10,
            "take_profit": 0.04,
            "stop_loss": 0.02,
            "martingale": True,
            "martingale_fator": 2.5,
        }

        # Configurações de IA
        self.IA_CONFIG = {
            "min_confianca": 0.80,
            "janela_analise": 100,
            "indicadores": ["RSI", "MACD", "Bollinger Bands", "Moving Averages"],
            "timeframes": ["1m", "5m", "15m", "1h"],
        }

        # Configurações de micro scalping
        self.MICRO_SCALPING = {
            "min_meta": 5.0,  # USD
            "max_meta": 50.0,  # USD
            "max_operacoes": 20,
            "intervalo_min": 60,  # segundos
            "take_profit": 0.01,  # 1%
            "stop_loss": 0.005,  # 0.5%
        }

        # Configurações de cache
        self.CACHE_CONFIG = {
            "enabled": True,
            "size": 1000,  # número máximo de itens
            "ttl": 3600,  # tempo de vida em segundos
            "cleanup_interval": 300,  # intervalo de limpeza em segundos
        }

        # Configurações de segurança
        self.SECURITY = {
            "max_login_attempts": 5,
            "lockout_time": 300,  # segundos
            "session_timeout": 3600,  # segundos
            "password_min_length": 8,
            "require_special_chars": True,
            "require_numbers": True,
            "require_uppercase": True,
        }

        # Carrega configurações do arquivo
        self.load_config()

    def load_config(self):
        """Carrega configurações do arquivo JSON"""
        config_file = os.path.join(self.DATA_DIR, "config.json")

        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    config_data = json.load(f)

                # Atualiza configurações com valores do arquivo
                for key, value in config_data.items():
                    if hasattr(self, key):
                        setattr(self, key, value)

            except Exception as e:
                logging.error(f"Erro ao carregar configurações: {str(e)}")

    def save_config(self):
        """Salva configurações em arquivo JSON"""
        config_file = os.path.join(self.DATA_DIR, "config.json")

        try:
            # Cria diretório se não existir
            os.makedirs(self.DATA_DIR, exist_ok=True)

            # Prepara dados para salvar
            config_data = {
                "DEBUG": self.DEBUG,
                "LOG_LEVEL": self.LOG_LEVEL,
                "TAKE_PROFIT": self.TAKE_PROFIT,
                "STOP_LOSS": self.STOP_LOSS,
                "MAX_OPERATIONS": self.MAX_OPERATIONS,
                "MIN_BALANCE": self.MIN_BALANCE,
                "MODO_INICIANTE": self.MODO_INICIANTE,
                "MODO_INTERMEDIARIO": self.MODO_INTERMEDIARIO,
                "MODO_AVANCADO": self.MODO_AVANCADO,
                "IA_CONFIG": self.IA_CONFIG,
                "MICRO_SCALPING": self.MICRO_SCALPING,
                "CACHE_CONFIG": self.CACHE_CONFIG,
                "SECURITY": self.SECURITY,
            }

            with open(config_file, "w") as f:
                json.dump(config_data, f, indent=4)

        except Exception as e:
            logging.error(f"Erro ao salvar configurações: {str(e)}")

    def get_modo_config(self, modo):
        """Retorna configurações específicas do modo de operação"""
        modos = {
            "iniciante": self.MODO_INICIANTE,
            "intermediario": self.MODO_INTERMEDIARIO,
            "avancado": self.MODO_AVANCADO,
        }

        return modos.get(modo.lower(), self.MODO_INICIANTE)

    def validate_config(self):
        """Valida as configurações"""
        try:
            # Valida valores numéricos
            assert self.TAKE_PROFIT > 0 and self.TAKE_PROFIT < 1
            assert self.STOP_LOSS > 0 and self.STOP_LOSS < 1
            assert self.MAX_OPERATIONS > 0
            assert self.MIN_BALANCE > 0

            # Valida modos de operação
            for modo in [
                self.MODO_INICIANTE,
                self.MODO_INTERMEDIARIO,
                self.MODO_AVANCADO,
            ]:
                assert modo["min_confianca"] > 0 and modo["min_confianca"] <= 1
                assert modo["max_operacoes"] > 0
                assert modo["take_profit"] > 0 and modo["take_profit"] < 1
                assert modo["stop_loss"] > 0 and modo["stop_loss"] < 1

            # Valida configurações de IA
            assert (
                self.IA_CONFIG["min_confianca"] > 0
                and self.IA_CONFIG["min_confianca"] <= 1
            )
            assert self.IA_CONFIG["janela_analise"] > 0
            assert len(self.IA_CONFIG["indicadores"]) > 0
            assert len(self.IA_CONFIG["timeframes"]) > 0

            # Valida configurações de micro scalping
            assert self.MICRO_SCALPING["min_meta"] > 0
            assert self.MICRO_SCALPING["max_meta"] > self.MICRO_SCALPING["min_meta"]
            assert self.MICRO_SCALPING["max_operacoes"] > 0
            assert self.MICRO_SCALPING["intervalo_min"] > 0
            assert (
                self.MICRO_SCALPING["take_profit"] > 0
                and self.MICRO_SCALPING["take_profit"] < 1
            )
            assert (
                self.MICRO_SCALPING["stop_loss"] > 0
                and self.MICRO_SCALPING["stop_loss"] < 1
            )

            # Valida configurações de cache
            assert self.CACHE_CONFIG["size"] > 0
            assert self.CACHE_CONFIG["ttl"] > 0
            assert self.CACHE_CONFIG["cleanup_interval"] > 0

            # Valida configurações de segurança
            assert self.SECURITY["max_login_attempts"] > 0
            assert self.SECURITY["lockout_time"] > 0
            assert self.SECURITY["session_timeout"] > 0
            assert self.SECURITY["password_min_length"] >= 8

            return True

        except AssertionError as e:
            logging.error(f"Erro na validação das configurações: {str(e)}")
            return False

    def update_config(self, new_config):
        """Atualiza configurações com novos valores"""
        try:
            for key, value in new_config.items():
                if hasattr(self, key):
                    setattr(self, key, value)

            if self.validate_config():
                self.save_config()
                return True
            return False

        except Exception as e:
            logging.error(f"Erro ao atualizar configurações: {str(e)}")
            return False

    def get_config_summary(self):
        """Retorna um resumo das configurações"""
        return {
            "modos": {
                "iniciante": self.MODO_INICIANTE,
                "intermediario": self.MODO_INTERMEDIARIO,
                "avancado": self.MODO_AVANCADO,
            },
            "ia": self.IA_CONFIG,
            "micro_scalping": self.MICRO_SCALPING,
            "security": self.SECURITY,
        }


# Instância global de configuração
config = Config()

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
