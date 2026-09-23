"""
Arquivo de configuração para o DerivBot
Contém constantes e configurações globais
"""

import os
import json
import logging
import secrets
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env (na raiz ou pasta config)
BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
root_env = os.path.join(BASE_DIR, ".env")
config_env = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(root_env):
    load_dotenv(root_env)
if os.path.exists(config_env):
    load_dotenv(config_env)


class ConfigMeta(type):
    """Metaclasse para expor propriedades dinâmicas no nível de classe de Config"""

    @property
    def ADMIN_LICENSES(cls) -> List[str]:
        return cls.obter_admin_licenses()


class Config(metaclass=ConfigMeta):
    # Versão do aplicativo
    VERSION = "2.0.0"

    # Diretórios - ajustado para a nova estrutura
    BASE_DIR = BASE_DIR
    DATA_DIR = os.path.join(BASE_DIR, "data")
    LOGS_DIR = os.path.join(BASE_DIR, "logs")

    # Cria diretórios se não existirem
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    # Configurações de logging
    LOG_CONFIG = {
        "level": os.getenv("LOG_LEVEL", "INFO"),  # DEBUG, INFO, WARNING, ERROR
        "file": os.path.join(LOGS_DIR, "derivbot.log"),
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "max_size": 10 * 1024 * 1024,  # 10MB
        "backup_count": 5,
        "console_output": True,
        "file_output": True,
    }

    # Configurações da API Deriv (Modelo Novo: Single PAT + OTP)
    DERIV_API_BASE = os.getenv("DERIV_API_BASE", "https://api.derivws.com")
    DERIV_APP_ID = os.getenv("DERIV_APP_ID", "")
    DERIV_PAT = os.getenv("DERIV_PAT", "")
    DERIV_WEBSOCKET_URL = os.getenv("DERIV_WEBSOCKET_URL", "wss://red.derivws.com/websockets/v3")

    # Configurações do servidor Flask
    FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    FLASK_PORT = int(os.getenv("FLASK_PORT", 5001))
    FLASK_DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

    # Configurações de segurança e admin
    MAX_LOGIN_ATTEMPTS = 5
    SESSION_TIMEOUT = 3600  # segundos
    PASSWORD_MIN_LENGTH = 8
    ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

    @classmethod
    def obter_admin_licenses(cls) -> List[str]:
        """
        Obtém licenças administrativas exclusivamente de fontes seguras externas:
        1. Variável de ambiente ADMIN_LICENSES (ex: 'LIC1,LIC2')
        2. Arquivo local de configuração ignorado pelo Git (data/admin_config.json)
        3. Fallback seguro: lista vazia [] (fail-closed, sem credenciais hardcoded)
        """
        env_val = os.getenv("ADMIN_LICENSES", "").strip()
        if env_val:
            return [lic.strip() for lic in env_val.split(",") if lic.strip()]

        admin_cfg_path = os.path.join(cls.DATA_DIR, "admin_config.json")
        if os.path.exists(admin_cfg_path):
            try:
                with open(admin_cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    file_licenses = cfg.get("admin_licenses", [])
                    if isinstance(file_licenses, list):
                        return [str(l).strip() for l in file_licenses if str(l).strip()]
            except Exception:
                pass

        return []

    @property
    def ADMIN_LICENSES(self) -> List[str]:
        """Propriedade para instâncias de Config"""
        return self.__class__.obter_admin_licenses()

    # Configurações de trading - DEMO POR PADRÃO (Issue #6)
    MODO_REAL_PADRAO = False  # Sempre inicia em DEMO por segurança
    TIMEFRAME_PADRAO = 1  # segundos
    MAX_OPERACOES_SIMULTANEAS = 10
    ATIVO_PADRAO = "1HZ75V"  # VIX75 para scalping

    # Configurações de indicadores técnicos
    INDICADORES = {
        "RSI": {"periodo": 14, "sobrecomprado": 70, "sobrevendido": 30},
        "BOLLINGER": {"periodo": 20, "desvio": 2},
        "EMA": {"rapida": 8, "lenta": 21},
    }

    # Configurações de email (opcional via .env)
    EMAIL_CONFIG = {
        "smtp_host": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", 587)),
        "smtp_user": os.getenv("SMTP_USER", ""),
        "smtp_pass": os.getenv("SMTP_PASS", ""),
    }

    # API Key do DeepSeek (opcional - via .env)
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
        "intermediario": {
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

    @classmethod
    def obter_deriv_pat(cls):
        """Retorna o token PAT configurado via .env, tokens.json ou licencas.json"""
        if cls.DERIV_PAT and str(cls.DERIV_PAT).strip():
            return str(cls.DERIV_PAT).strip()
        tokens = cls.carregar_tokens()
        if tokens.get("deriv_pat"):
            return str(tokens["deriv_pat"]).strip()
        lic_file = os.path.join(cls.DATA_DIR, "licencas.json")
        if os.path.exists(lic_file):
            try:
                with open(lic_file, "r") as f:
                    lics = json.load(f)
                    for l in lics.values():
                        pat = (
                            l.get("deriv_pat")
                            or l.get("token_deriv_demo")
                            or l.get("token_deriv_real")
                        )
                        if pat:
                            return str(pat).strip()
            except Exception:
                pass
        return ""

    @classmethod
    def obter_deriv_app_id(cls):
        """Retorna o DERIV_APP_ID configurado via .env"""
        return str(cls.DERIV_APP_ID).strip() if cls.DERIV_APP_ID else os.getenv("DERIV_APP_ID", "")

    @staticmethod
    def carregar_tokens():
        """
        Carrega o token Deriv salvo (Modelo Canônico: deriv_pat).

        Returns:
            dict: Dicionário contendo 'deriv_pat' e retrocompatibilidade
        """
        tokens_file = os.path.join(Config.DATA_DIR, "tokens.json")

        if os.path.exists(tokens_file):
            try:
                with open(tokens_file, "r") as f:
                    data = json.load(f)
                    # Migração transparente se contiver campos legados
                    if "deriv_pat" not in data:
                        pat_antigo = data.get("token_deriv") or data.get("token_demo") or data.get("token_real")
                        if pat_antigo:
                            data["deriv_pat"] = pat_antigo
                    return data
            except Exception as e:
                logging.error(f"Erro ao carregar tokens: {e}")

        return {"deriv_pat": None}

    @staticmethod
    def salvar_tokens(deriv_pat=None, **kwargs):
        """
        Salva o PAT único da Deriv.

        Args:
            deriv_pat: Personal Access Token (PAT) único
            **kwargs: Suporte temporário a argumentos legados para compatibilidade
        """
        tokens = Config.carregar_tokens()

        token_a_salvar = deriv_pat or kwargs.get("token_demo") or kwargs.get("token_real") or kwargs.get("token_deriv")
        if token_a_salvar:
            tokens["deriv_pat"] = str(token_a_salvar).strip()

        tokens_file = os.path.join(Config.DATA_DIR, "tokens.json")

        try:
            with open(tokens_file, "w") as f:
                json.dump(tokens, f, indent=2)
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


# Constantes para módulos de análise técnica e inteligência
CONFIG_MICRO_SCALPING_ANALISE = {
    "suporte_resistencia_janela_velas": 5,
    "suporte_resistencia_margem_percent": 0.03,
    "meta_progresso_reducao_ops_percent": 75.0,
    "rsi_sobrecompra_limiar": 70,
    "rsi_sobrevenda_limiar": 30,
    "suporte_resistencia_janela": 5,
    "suporte_resistencia_margem": 0.03,
    "rsi_sobrecompra": 70,
    "rsi_sobrevenda": 30,
    "meta_minima": 10.0,
    "meta_progresso_reducao": 75.0,
    "duracao_operacao": 1,
    "multiplier_padrao": 1,
    "ativo_padrao": "R_10",
}

RSI_PERIODO_PADRAO = 14
RSI_SOBRECOMPRADO_PADRAO = 70
RSI_SOBREVENDIDO_PADRAO = 30
BOLLINGER_PERIODO_PADRAO = 20
BOLLINGER_DESVIO_PADRAO = 2.0
EMA_RAPIDA_PADRAO = 8
EMA_LENTA_PADRAO = 21

CONFIG_ANALISE_CATALOGADOR = {
    "limites": {
        "min_velas_analise": 10,
    }
}

CONFIG_ESTRATEGIA_TURBO = {
    "indicadores": {
        "rsi_periodo": 14,
    }
}

# Percentuais canônicos de meta por modo (Issue #23.E)
PERCENTUAL_META_POR_MODO = {
    "iniciante": 0.20,
    "intermediario": 0.50,
    "conservador": 0.50,
    "agressivo": 1.00,
}

def calcular_meta_sessao(saldo: float, modo: Optional[str] = "iniciante") -> float:
    """Calcula a meta da sessão a partir da banca real e do perfil."""
    modo_norm = normalizar_modo_operacao(modo)
    pct = PERCENTUAL_META_POR_MODO.get(modo_norm, 0.20)
    return round(float(saldo) * pct, 2)

def calcular_valor_operacao(meta: float, minimo_contrato: float = 0.35) -> Tuple[float, float, bool]:
    """
    Retorna (valor_operacao_teorico, valor_operacao_efetivo, foi_elevado_pelo_minimo).
    Fórmula: 1% da meta da sessão, respeitando o mínimo real do contrato Deriv.
    """
    valor_teorico = round(float(meta) * 0.01, 2)
    valor_efetivo = max(valor_teorico, float(minimo_contrato))
    foi_elevado = valor_efetivo > valor_teorico
    return valor_teorico, valor_efetivo, foi_elevado

# Limites canônicos de concorrência por perfil (Issue #20 / #23)
LIMITES_CONCORRENCIA_POR_MODO = {
    "iniciante": 3,
    "intermediario": 5,
    "conservador": 5,  # Alias compatível
    "agressivo": 10,
}

def normalizar_modo_operacao(modo: Optional[str]) -> str:
    """
    Normaliza o identificador de perfil de operação.
    'conservador' é tratado como alias compatível para 'intermediario'.
    """
    if not modo:
        return "iniciante"
    m = str(modo).strip().lower()
    if m == "conservador":
        return "intermediario"
    if m in LIMITES_CONCORRENCIA_POR_MODO:
        return m
    return "iniciante"

def obter_limite_posicoes(modo: Optional[str] = None) -> int:
    """
    Retorna o limite canônico de operações simultâneas para o perfil especificado:
    - Iniciante: até 3 posições
    - Intermediário (ou conservador): até 5 posições
    - Agressivo: até 10 posições
    """
    if not modo:
        return LIMITES_CONCORRENCIA_POR_MODO["iniciante"]
    m = normalizar_modo_operacao(modo)
    return LIMITES_CONCORRENCIA_POR_MODO.get(m, LIMITES_CONCORRENCIA_POR_MODO["iniciante"])

MODOS_OPERACAO_SCALPING = {
    "iniciante": {
        "max_operacoes_simultaneas": 3,
        "confianca_min_sinal": 0.7,
    },
    "intermediario": {
        "max_operacoes_simultaneas": 5,
        "confianca_min_sinal": 0.8,
    },
    "conservador": {
        "max_operacoes_simultaneas": 5,
        "confianca_min_sinal": 0.8,
    },
    "agressivo": {
        "max_operacoes_simultaneas": 10,
        "confianca_min_sinal": 0.6,
    },
}

# ==============================================================================
# CONFIGURAÇÃO DO MICRO-SCALPER SELETIVO (Issues #2, #3, #4, #20)
# ==============================================================================
MICRO_SCALPER_CONFIG = {
    # Concorrência máxima global de 3 posições no modo rápido (Issue #23)
    "max_open_positions": 3,
    "allow_martingale": False,
    "max_martingale_steps": 0,
    "martingale_multiplier": 1.0,

    # 3. DETECTOR DE EXTREMOS
    "extremo": {
        "percentile_low": float(os.getenv("SCALPER_PERCENTILE_LOW", "5.0")),
        "percentile_high": float(os.getenv("SCALPER_PERCENTILE_HIGH", "95.0")),
        "z_score_threshold": float(os.getenv("SCALPER_Z_SCORE_THRESHOLD", "2.0")),
        "janela_curta": int(os.getenv("SCALPER_JANELA_CURTA", "20")),
        "janela_media": int(os.getenv("SCALPER_JANELA_MEDIA", "60")),
        "janela_longa": int(os.getenv("SCALPER_JANELA_LONGA", "120")),
        "rsi_oversold": float(os.getenv("SCALPER_RSI_OVERSOLD", "25.0")),
        "rsi_overbought": float(os.getenv("SCALPER_RSI_OVERBOUGHT", "75.0")),
        "bb_period": int(os.getenv("SCALPER_BB_PERIOD", "20")),
        "bb_std": float(os.getenv("SCALPER_BB_STD", "2.0")),
        "ema_fast": int(os.getenv("SCALPER_EMA_FAST", "8")),
        "ema_slow": int(os.getenv("SCALPER_EMA_SLOW", "21")),
    },

    # 4. NÃO COMPRAR EM QUEDA SEM CONFIRMAÇÃO DE REVERSÃO
    "reversao": {
        "min_reversal_ticks": int(os.getenv("SCALPER_MIN_REVERSAL_TICKS", "3")),
        "rsi_exit_margin": float(os.getenv("SCALPER_RSI_EXIT_MARGIN", "2.0")),
        "min_ticks_desaceleracao": int(os.getenv("SCALPER_MIN_TICKS_DESACELERACAO", "2")),
    },

    # 5. SCORE DE CONFLUÊNCIA
    "score": {
        "min_score": float(os.getenv("SCALPER_MIN_SCORE", "85.0")),
        "pesos": {
            "extremo_estatistico": 25.0,  # percentil + z-score
            "bollinger": 15.0,           # toque / rompimento de banda extrema
            "rsi_extremo": 15.0,          # rsi sobrevendido/sobrecomprado
            "distancia_ema": 15.0,        # esticamento em relação às EMAs
            "confirmacao_reversao": 20.0, # esgotamento + virada de ticks
            "saude_mercado": 10.0,        # volatilidade adequada + integridade dos dados
        },
    },

    # 8. GATEWAY DE RISCO
    "gateway_risco": {
        "min_buffer_ticks": 30,
        "max_spread_pct": 0.005,
        "tempo_max_tick_stale_s": 2.5,
        "min_balance_usd": 1.0,
    },

    # 11 & 12. SAÍDA NO PRIMEIRO LUCRO LÍQUIDO
    "saida": {
        "exit_mode": os.getenv("SCALPER_EXIT_MODE", "FIRST_POSITIVE_PROFIT"),
        "min_exit_profit": float(os.getenv("SCALPER_MIN_EXIT_PROFIT", "0.02")),
        "min_positive_updates": int(os.getenv("SCALPER_MIN_POSITIVE_UPDATES", "2")),
        "max_hold_seconds": int(os.getenv("SCALPER_MAX_HOLD_SECONDS", "45")),
    },

    # 17. COOLDOWN
    "cooldown": {
        "tempo_minimo_segundos": int(os.getenv("SCALPER_COOLDOWN_SECONDS", "25")),
    },

    # 18. TELEMETRIA
    "telemetria": {
        "log_todas_oportunidades": True,
        "max_historico_telemetria": 500,
    },
}

# Vincula na classe Config para compatibilidade direta
Config.MICRO_SCALPER = MICRO_SCALPER_CONFIG
Config.LIMITES_CONCORRENCIA_POR_MODO = LIMITES_CONCORRENCIA_POR_MODO
Config.obter_limite_posicoes = staticmethod(obter_limite_posicoes)
Config.normalizar_modo_operacao = staticmethod(normalizar_modo_operacao)
Config.MAX_OPEN_POSITIONS = 3
Config.PERCENTUAL_META_POR_MODO = PERCENTUAL_META_POR_MODO
Config.calcular_meta_sessao = staticmethod(calcular_meta_sessao)
Config.calcular_valor_operacao = staticmethod(calcular_valor_operacao)


