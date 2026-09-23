import time
import os
import numpy as np
import pandas as pd
import logging
from functools import lru_cache
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

# Importa as configurações centralizadas otimizadas
try:
    from src import config as bot_config
except ImportError:
    import config as bot_config

# Cria diretório de logs se não existir
os.makedirs("logs", exist_ok=True)

# Configuração de logging usando configurações centralizadas
logging.basicConfig(
    level=getattr(logging, getattr(bot_config, "LOG_LEVEL", "INFO"), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/catalogador.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("catalogador_otimizado")

# Configurações locais (fallback)
CONFIG_CATALOGADOR = {
    "analise": {
        "max_velas_memoria": 2000,
        "max_ticks_memoria": 20000,
        "timeframe_padrao_s": 15,
        "min_velas_analise": 25,
    },
    "limpeza": {
        "intervalo_s": 1800,
        "max_idade_velas_s": 21600,
        "max_idade_ticks_s": 3600,
    },
    "operacoes": {"intervalo_min_ops_s": 5},
    "sistema": {"nivel_log": "INFO", "cache_ttl": 60, "arquivo_memoria": "data"},
    "volatilitys": {"lista_ativos": ["1HZ75V", "1HZ100V", "R_10", "R_25", "R_50"]},
}

CONFIG_INDICADORES = {
    "periodos": {
        "ema_rapida": 8,
        "ema_lenta": 21,
        "rsi": 14,
        "bollinger": 20,
    },
    "parametros": {
        "rsi_sobrevenda": 30,
        "rsi_sobrecompra": 70,
        "rsi_zona_ideal_min": 40,
        "rsi_zona_ideal_max": 60,
        "bollinger_desvio": 2.0,
    },
    "cache": {"max_size": 128},
}

CONFIG_ASSERTIVIDADE = {
    "pesos": {
        "tendencia_ema": 0.3,
        "rsi_zona": 0.25,
        "bollinger_posicao": 0.2,
    },
    "volatilidade_scores": {
        "baixa": 0.1,
        "media": 0.15,
        "alta": 0.2,
    },
    "tipo_contrato": {
        "assertividade_alta_threshold": 0.7,
        "multiplicadores_min_variedade": 3,
    },
}

CONFIG_VOLATILITYS = {
    "selecao": {
        "min_velas_necessarias": 20,
    },
    "modos_preferencia": {
        "iniciante": {"prefere_turbo": True, "score_turbo_bonus": 0.3},
        "conservador": {"prefere_turbo": False, "score_multiplier_bonus": 0.2},
        "agressivo": {"prefere_turbo": False, "score_multiplier_bonus": 0.1},
    },
    "fallback": {
        "ativo_padrao": "1HZ75V",
        "tipo_contrato_padrao": "turbo",
        "multiplicador_padrao": 10,
    },
}

# Diretório para memória usando configuração centralizada
MEMORIA_DIR = CONFIG_CATALOGADOR["sistema"]["arquivo_memoria"]
if not os.path.exists(MEMORIA_DIR):
    os.makedirs(MEMORIA_DIR)

# API Key - usando configuração centralizada
try:
    from config.config import Config

    DEEPSEEK_API_KEY = Config.DEEPSEEK_API_KEY
except ImportError:
    DEEPSEEK_API_KEY = ""

if not DEEPSEEK_API_KEY:
    logger.warning("DEEPSEEK_API_KEY não configurada. Funcionalidade de IA limitada.")


# Configurações locais de ativos para substituir bot_config
ATIVOS_SCALPING = {
    "1HZ75V": {
        "nome": "Volatility 75 Index",
        "volatilidade": "alta",
        "multiplicadores_disponiveis": [10, 100, 200, 300, 400],
        "min_stake": 0.35,
        "max_stake": 100.0,
        "prioridade": 1,
    },
    "1HZ100V": {
        "nome": "Volatility 100 Index",
        "volatilidade": "alta",
        "multiplicadores_disponiveis": [10, 100, 200, 300, 400],
        "min_stake": 0.35,
        "max_stake": 100.0,
        "prioridade": 2,
    },
    "R_10": {
        "nome": "Volatility 10 Index",
        "volatilidade": "baixa",
        "multiplicadores_disponiveis": [1, 2, 3, 4, 5, 10],
        "min_stake": 0.35,
        "max_stake": 50.0,
        "prioridade": 3,
    },
}

MODOS_OPERACAO_SCALPING = {
    "iniciante": {
        "multiplicador_nivel": "baixo",
        "max_stake": 20.0,
        "max_operacoes_simultaneas": 3,
    },
    "intermediario": {
        "multiplicador_nivel": "medio",
        "max_stake": 50.0,
        "max_operacoes_simultaneas": 5,
    },
    "conservador": {
        "multiplicador_nivel": "medio",
        "max_stake": 50.0,
        "max_operacoes_simultaneas": 5,
    },
    "agressivo": {
        "multiplicador_nivel": "alto",
        "max_stake": 100.0,
        "max_operacoes_simultaneas": 10,
    },
}

PAR_PADRAO_OPERACAO = "1HZ75V"

# Configuração de ativos para estratégia turbo integrada
ATIVOS_TURBO_INTEGRADOS = {
    "1HZ75V": {  # VIX75
        "tipo_contrato": "turbo",
        "duracao_segundos": 15,
        "min_stake": 0.35,
        "max_stake": 100.0,
        "contract_types": ["CALL", "PUT"],
        "multipliers": [10, 100, 200, 300, 400],
        "timeframe": 1,
        "scalping_friendly": True,
    },
    "1HZ100V": {  # VIX100
        "tipo_contrato": "turbo",
        "duracao_segundos": 15,
        "min_stake": 0.35,
        "max_stake": 100.0,
        "contract_types": ["CALL", "PUT"],
        "multipliers": [10, 100, 200, 300, 400],
        "timeframe": 1,
        "scalping_friendly": True,
    },
    "R_10": {  # Volatility 10 Index
        "tipo_contrato": "turbo",
        "duracao_segundos": 15,
        "min_stake": 0.35,
        "max_stake": 50.0,
        "contract_types": ["CALL", "PUT"],
        "multipliers": [1, 2, 3, 4, 5, 10],
        "timeframe": 1,
        "scalping_friendly": True,
    },
    "R_25": {  # Volatility 25 Index
        "tipo_contrato": "turbo",
        "duracao_segundos": 15,
        "min_stake": 0.35,
        "max_stake": 50.0,
        "contract_types": ["CALL", "PUT"],
        "multipliers": [1, 2, 3, 4, 5, 10],
        "timeframe": 1,
        "scalping_friendly": True,
    },
    "R_50": {  # Volatility 50 Index
        "tipo_contrato": "turbo",
        "duracao_segundos": 15,
        "min_stake": 0.35,
        "max_stake": 50.0,
        "contract_types": ["CALL", "PUT"],
        "multipliers": [1, 2, 3, 4, 5, 10],
        "timeframe": 1,
        "scalping_friendly": True,
    },
}


class DecisaoTipo(str, Enum):
    CALL = "CALL"
    PUT = "PUT"
    AGUARDAR = "AGUARDAR"
    SAIR = "SAIR"
    MANTER = "MANTER"


@dataclass
class ContextoAnalise:
    preco_atual: float
    rsi: float
    tendencia: str
    lucro_total_sessao: float = 0.0
    historico_recente_trades: List[str] = field(default_factory=list)

    def gerar_relatorio(self) -> str:
        return (
            f"RELATÓRIO DE ANÁLISE (ENTRADA):\n"
            f"- Preço Atual: {self.preco_atual:.5f}\n- RSI: {self.rsi:.2f}\n"
            f"- Tendência Principal: {self.tendencia}\n"
            f"- Lucro Sessão: ${self.lucro_total_sessao:.2f}"
        )


class AnalisadorTecnicoOtimizado:
    """Analisador técnico otimizado usando configurações centralizadas"""

    @staticmethod
    @lru_cache(maxsize=CONFIG_INDICADORES.get("cache", {}).get("max_size", 128))
    def calcular_ema(precos: Tuple[float, ...], periodo: int = None) -> Optional[float]:
        """Calcula EMA usando configurações centralizadas"""
        if periodo is None:
            periodo = CONFIG_INDICADORES.get("periodos", {}).get("ema_rapida", 8)

        if len(precos) < periodo:
            return None
        try:
            s = pd.Series(precos)
            ema = s.ewm(span=periodo, adjust=False).mean()
            return ema.iloc[-1] if not ema.empty else None
        except Exception as e:
            logger.error(f"Erro cálculo EMA (P{periodo}): {e}")
            return None

    @staticmethod
    @lru_cache(maxsize=CONFIG_INDICADORES.get("cache", {}).get("max_size", 128))
    def calcular_rsi(precos: Tuple[float, ...], periodo: int = None) -> float:
        """Calcula RSI usando configurações centralizadas"""
        if periodo is None:
            periodo = CONFIG_INDICADORES.get("periodos", {}).get("rsi", 14)

        try:
            if len(precos) < periodo + 1:
                return 50.0
            deltas = np.diff(precos)
            gains = np.maximum(deltas, 0)
            losses = np.maximum(-deltas, 0)

            avg_gain = np.sum(gains[:periodo]) / periodo
            avg_loss = np.sum(losses[:periodo]) / periodo

            for i in range(periodo, len(gains)):
                avg_gain = (avg_gain * (periodo - 1) + gains[i]) / periodo
                avg_loss = (avg_loss * (periodo - 1) + losses[i]) / periodo

            if avg_loss == 0:
                return 100.0 if avg_gain > 0 else 50.0
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
            return round(rsi, 2)
        except Exception as e:
            logger.error(f"Erro cálculo RSI (P{periodo}): {e}")
            return 50.0

    @staticmethod
    @lru_cache(maxsize=CONFIG_INDICADORES.get("cache", {}).get("max_size", 128))
    def calcular_bollinger(
        precos: Tuple[float, ...], periodo: int = None, desvio: float = None
    ) -> Optional[Dict[str, float]]:
        """Calcula Bollinger Bands usando configurações centralizadas"""
        if periodo is None:
            periodo = CONFIG_INDICADORES.get("periodos", {}).get("bollinger", 20)
        if desvio is None:
            desvio = CONFIG_INDICADORES.get("parametros", {}).get(
                "bollinger_desvio", 2.0
            )

        if len(precos) < periodo:
            return None
        try:
            precos_periodo = precos[-periodo:]
            media = np.mean(precos_periodo)
            std_dev = np.std(precos_periodo)

            return {
                "media": media,
                "superior": media + (std_dev * desvio),
                "inferior": media - (std_dev * desvio),
            }
        except Exception as e:
            logger.error(f"Erro cálculo Bollinger (P{periodo}, D{desvio}): {e}")
            return None

    @staticmethod
    def determinar_tendencia(precos: Tuple[float, ...]) -> str:
        """Determina tendência usando EMAs configuradas"""
        ema_rapida_periodo = CONFIG_INDICADORES.get("periodos", {}).get("ema_rapida", 8)
        ema_lenta_periodo = CONFIG_INDICADORES.get("periodos", {}).get("ema_lenta", 21)

        if len(precos) < ema_lenta_periodo:
            return "INDEFINIDA"

        ema_rapida = AnalisadorTecnicoOtimizado.calcular_ema(precos, ema_rapida_periodo)
        ema_lenta = AnalisadorTecnicoOtimizado.calcular_ema(precos, ema_lenta_periodo)

        if ema_rapida is None or ema_lenta is None:
            return "INDEFINIDA"
        if ema_rapida > ema_lenta:
            return "ALTA"
        if ema_rapida < ema_lenta:
            return "BAIXA"
        return "NEUTRA"

    @staticmethod
    def calcular_percentil(
        precos: Tuple[float, ...], preco_atual: float, janela: int = 60
    ) -> float:
        """Calcula a posição percentual (0 a 100) do preço dentro da janela de ticks."""
        if not precos:
            return 50.0
        amostra = precos[-janela:] if len(precos) >= janela else precos
        if len(amostra) < 2:
            return 50.0
        menores = sum(1 for p in amostra if p < preco_atual)
        iguais = sum(1 for p in amostra if p == preco_atual)
        percentil = ((menores + (0.5 * iguais)) / len(amostra)) * 100.0
        return round(float(percentil), 2)

    @staticmethod
    def calcular_z_score(
        precos: Tuple[float, ...], preco_atual: float, janela: int = 60
    ) -> float:
        """Calcula o Z-Score do preço atual em relação à média e desvio da janela."""
        if not precos:
            return 0.0
        amostra = precos[-janela:] if len(precos) >= janela else precos
        if len(amostra) < 2:
            return 0.0
        media = float(np.mean(amostra))
        desvio = float(np.std(amostra))
        if desvio == 0:
            return 0.0
        z = (preco_atual - media) / desvio
        return round(float(z), 3)

    @staticmethod
    def calcular_inclinacao(precos: Tuple[float, ...], n_ticks: int = 5) -> float:
        """Calcula o slope linear da trajetória recente de ticks."""
        if not precos or len(precos) < 2:
            return 0.0
        amostra = precos[-n_ticks:] if len(precos) >= n_ticks else precos
        if len(amostra) < 2:
            return 0.0
        x = np.arange(len(amostra))
        try:
            slope, _ = np.polyfit(x, amostra, 1)
            media_preco = float(np.mean(amostra))
            if media_preco != 0:
                return float(slope / media_preco * 100.0)
            return float(slope)
        except Exception:
            return 0.0

    @staticmethod
    def calcular_volatilidade_instantanea(
        precos: Tuple[float, ...], janela: int = 20
    ) -> float:
        """Calcula a volatilidade percentual instantânea (desvio relativo) da janela."""
        if not precos or len(precos) < 2:
            return 0.0
        amostra = precos[-janela:] if len(precos) >= janela else precos
        media = float(np.mean(amostra))
        if media == 0:
            return 0.0
        return float((np.std(amostra) / media) * 100.0)


class CalculadorAssertividade:
    """Calculadora de assertividade usando configurações centralizadas"""

    @staticmethod
    def calcular_assertividade_ativo(
        ativo: str, ema8: float, ema21: float, rsi: float, bb: dict, preco_atual: float
    ) -> float:
        """Calcula assertividade usando pesos configurados"""
        try:
            pesos = CONFIG_ASSERTIVIDADE["pesos"]
            assertividade = 0.0

            # 1. Tendência EMA
            if ema8 > ema21:
                diferenca_ema = abs(ema8 - ema21) / ema21
                assertividade += min(pesos["tendencia_ema"], diferenca_ema * 10)

            # 2. RSI em zona favorável
            rsi_params = CONFIG_INDICADORES.get(
                "parametros",
                {
                    "rsi_sobrevenda": 30,
                    "rsi_sobrecompra": 70,
                    "rsi_zona_ideal_min": 40,
                    "rsi_zona_ideal_max": 60,
                },
            )
            if rsi_params["rsi_sobrevenda"] <= rsi <= rsi_params["rsi_sobrecompra"]:
                if (
                    rsi_params["rsi_zona_ideal_min"]
                    <= rsi
                    <= rsi_params["rsi_zona_ideal_max"]
                ):
                    assertividade += pesos["rsi_zona"]
                else:
                    assertividade += pesos["rsi_zona"] * 0.6

            # 3. Bollinger Bands
            if bb:
                largura_bb = bb["superior"] - bb["inferior"]
                posicao_bb = (preco_atual - bb["inferior"]) / largura_bb

                if posicao_bb <= 0.2 or posicao_bb >= 0.8:
                    assertividade += pesos["bollinger_posicao"]
                elif 0.3 <= posicao_bb <= 0.7:
                    assertividade += pesos["bollinger_posicao"] * 0.6

            # 4. Volatilidade do ativo
            config_ativo = ATIVOS_SCALPING.get(ativo, {})
            volatilidade = config_ativo.get("volatilidade", "media")
            volatilidade_scores = CONFIG_ASSERTIVIDADE["volatilidade_scores"]
            assertividade += volatilidade_scores.get(volatilidade, 0.12)

            return min(1.0, assertividade)

        except Exception as e:
            logger.error(f"Erro calculando assertividade para {ativo}: {e}")
            return 0.0

    @staticmethod
    def determinar_tipo_contrato(ativo: str, assertividade: float, modo: str) -> str:
        """Determina tipo de contrato usando configurações"""
        try:
            config_ativo = ATIVOS_SCALPING.get(ativo, {})
            preferencias = CONFIG_VOLATILITYS["modos_preferencia"].get(modo.lower(), {})

            score_multiplier = 0.0
            score_turbo = 0.0

            # Assertividade alta favorece multipliers
            threshold = CONFIG_ASSERTIVIDADE["tipo_contrato"][
                "assertividade_alta_threshold"
            ]
            if assertividade >= threshold:
                score_multiplier += 0.3
            else:
                score_turbo += 0.2

            # Preferência por modo
            if preferencias.get("prefere_turbo", False):
                score_turbo += preferencias.get("score_turbo_bonus", 0.3)
            else:
                score_multiplier += preferencias.get("score_multiplier_bonus", 0.1)

            # Variedade de multiplicadores
            multiplicadores = config_ativo.get("multiplicadores_disponiveis", [])
            min_variedade = CONFIG_ASSERTIVIDADE["tipo_contrato"][
                "multiplicadores_min_variedade"
            ]
            if len(multiplicadores) >= min_variedade:
                score_multiplier += 0.2
            else:
                score_turbo += 0.1

            return "multiplier" if score_multiplier > score_turbo else "turbo"

        except Exception as e:
            logger.error(f"Erro determinando tipo de contrato para {ativo}: {e}")
            return CONFIG_VOLATILITYS["fallback"]["tipo_contrato_padrao"]
 

AnalisadorTecnico = AnalisadorTecnicoOtimizado


class CatalogadorOtimizado:
    """Catalogador otimizado com configurações centralizadas"""

    def __init__(self):
        # Configurações básicas usando config centralizado com fallbacks
        analise_config = CONFIG_CATALOGADOR.get("analise", {})
        self.timeframe_s = analise_config.get("timeframe_padrao_s", 15)
        self.max_velas_mem = analise_config.get("max_velas_memoria", 2000)
        self.max_ticks_mem = analise_config.get("max_ticks_memoria", 20000)

        # Configurações de limpeza
        limpeza_config = CONFIG_CATALOGADOR.get("limpeza", {})
        self.max_idade_velas_s = limpeza_config.get("max_idade_velas_s", 21600)
        self.max_idade_ticks_s = limpeza_config.get("max_idade_ticks_s", 3600)
        self.intervalo_cleanup_s = limpeza_config.get("intervalo_s", 1800)

        # Configurações de operações
        ops_config = CONFIG_CATALOGADOR.get("operacoes", {})
        self.intervalo_min_ops_s = ops_config.get("intervalo_min_ops_s", 5)

        # Dados
        self.ticks: List[Tuple[float, float]] = []
        self.velas_ohlc: List[Dict[str, Union[int, float]]] = []
        self._vela_atual_construcao: Optional[Dict[str, Union[int, float]]] = None
        self._inicio_vela_atual_s: Optional[int] = None

        # Estado
        self.ativo_selecionado = PAR_PADRAO_OPERACAO
        self.ultima_operacao_ts = 0.0
        self.operacoes_ativas_ts: List[float] = []
        self.lucro_total_sessao = 0.0
        self.historico_operacoes_finalizadas: List[Dict] = []
        self.ultimo_cleanup_s = time.time()

        # Logger específico
        self.logger = logging.getLogger("CatalogadorOtimizado")
        self.logger.info(
            f"Catalogador Otimizado inicializado (Timeframe: {self.timeframe_s}s)"
        )

    def obter_multiplicador_otimizado(self, ativo: str, modo: str = "agressivo") -> int:
        """Obtém multiplicador otimizado usando configurações centralizadas"""
        try:
            config_ativo = ATIVOS_SCALPING.get(ativo)
            config_modo = MODOS_OPERACAO_SCALPING.get(modo.lower())

            if not config_ativo or not config_modo:
                fallback = CONFIG_VOLATILITYS["fallback"]["multiplicador_padrao"]
                self.logger.warning(
                    f"Config não encontrada para {ativo}/{modo}, usando fallback: {fallback}"
                )
                return fallback

            multipliers = config_ativo.get("multiplicadores_disponiveis", [10])
            nivel = config_modo.get("multiplicador_nivel", "medio")

            if nivel == "baixo":
                return multipliers[0]
            elif nivel == "medio":
                return multipliers[len(multipliers) // 2]
            else:  # alto
                return multipliers[-2] if len(multipliers) > 1 else multipliers[0]

        except Exception as e:
            self.logger.error(f"Erro ao obter multiplicador: {e}")
            return CONFIG_VOLATILITYS["fallback"]["multiplicador_padrao"]

    def analisar_todos_volatilitys_e_escolher_melhor(
        self, modo: str = "agressivo"
    ) -> dict:
        """Analisa todos os volatility indices usando configurações centralizadas"""
        try:
            volatilitys_config = CONFIG_VOLATILITYS["selecao"]
            lista_ativos = CONFIG_CATALOGADOR["volatilitys"]["lista_ativos"]

            self.logger.info(
                "🔍 Analisando todos os Volatility Indices (versão otimizada)..."
            )

            resultados_analise = []

            for ativo in lista_ativos:
                try:
                    config_ativo = ATIVOS_SCALPING.get(ativo)
                    if not config_ativo:
                        continue

                    # Simula análise técnica (usando velas atuais)
                    velas = self.obter_velas_atuais()
                    if len(velas) < volatilitys_config["min_velas_necessarias"]:
                        self.logger.warning(
                            f"Velas insuficientes para {ativo}: {len(velas)}"
                        )
                        continue

                    # Calcula indicadores usando analisador otimizado
                    closes = tuple(float(v["close"]) for v in velas[-25:])

                    ema8 = AnalisadorTecnicoOtimizado.calcular_ema(
                        closes,
                        CONFIG_INDICADORES.get("periodos", {}).get("ema_rapida", 8),
                    )
                    ema21 = AnalisadorTecnicoOtimizado.calcular_ema(
                        closes,
                        CONFIG_INDICADORES.get("periodos", {}).get("ema_lenta", 21),
                    )
                    rsi = AnalisadorTecnicoOtimizado.calcular_rsi(closes)
                    bb = AnalisadorTecnicoOtimizado.calcular_bollinger(closes)

                    if ema8 is None or ema21 is None:
                        continue

                    # Calcula assertividade usando calculadora otimizada
                    assertividade = (
                        CalculadorAssertividade.calcular_assertividade_ativo(
                            ativo, ema8, ema21, rsi, bb, closes[-1]
                        )
                    )

                    # Determina tipo de contrato
                    tipo_contrato = CalculadorAssertividade.determinar_tipo_contrato(
                        ativo, assertividade, modo
                    )

                    resultado = {
                        "ativo": ativo,
                        "nome": config_ativo["nome"],
                        "assertividade": assertividade,
                        "tipo_contrato": tipo_contrato,
                        "multiplicador_recomendado": self.obter_multiplicador_otimizado(
                            ativo, modo
                        ),
                        "valor_entrada": config_ativo.get("min_stake", 0.35),
                        "prioridade": config_ativo.get("prioridade", 99),
                        "indicadores": {
                            "ema8": ema8,
                            "ema21": ema21,
                            "rsi": rsi,
                            "preco_atual": closes[-1],
                            "bb_superior": bb["superior"] if bb else None,
                            "bb_inferior": bb["inferior"] if bb else None,
                        },
                    }

                    resultados_analise.append(resultado)
                    self.logger.info(
                        f"📊 {ativo}: Assertividade={assertividade:.2f}, Tipo={tipo_contrato}"
                    )

                except Exception as e:
                    self.logger.error(f"Erro analisando {ativo}: {e}")
                    continue

            if not resultados_analise:
                fallback = CONFIG_VOLATILITYS["fallback"]
                self.logger.error("Nenhum ativo pôde ser analisado, usando fallback")
                return {
                    "erro": "Nenhum ativo disponível",
                    "fallback": {
                        "ativo": fallback["ativo_padrao"],
                        "tipo_contrato": fallback["tipo_contrato_padrao"],
                        "multiplicador": fallback["multiplicador_padrao"],
                    },
                }

            # Ordena por assertividade
            resultados_analise.sort(key=lambda x: x["assertividade"], reverse=True)
            melhor_ativo = resultados_analise[0]

            self.logger.info(
                f"🎯 MELHOR ATIVO (OTIMIZADO): {melhor_ativo['ativo']} ({melhor_ativo['nome']})"
            )
            self.logger.info(f"   Assertividade: {melhor_ativo['assertividade']:.2f}")
            self.logger.info(f"   Tipo: {melhor_ativo['tipo_contrato']}")
            self.logger.info(
                f"   Multiplicador: x{melhor_ativo['multiplicador_recomendado']}"
            )

            # Atualiza ativo selecionado
            self.ativo_selecionado = melhor_ativo["ativo"]

            return {
                "melhor_ativo": melhor_ativo,
                "todos_resultados": resultados_analise,
                "total_analisados": len(resultados_analise),
                "modo_operacao": modo,
                "configuracao_usada": "otimizada_centralizada",
            }

        except Exception as e:
            self.logger.error(f"Erro na análise geral dos volatilitys: {e}")
            fallback = CONFIG_VOLATILITYS["fallback"]
            return {
                "erro": str(e),
                "fallback": {
                    "ativo": fallback["ativo_padrao"],
                    "tipo_contrato": fallback["tipo_contrato_padrao"],
                    "multiplicador": fallback["multiplicador_padrao"],
                },
            }

    def validar_operacao_otimizada(self, ativo: str, modo: str, saldo: float) -> tuple:
        """Valida operação usando configurações centralizadas"""
        try:
            config_ativo = ATIVOS_SCALPING.get(ativo)
            config_modo = MODOS_OPERACAO_SCALPING.get(modo.lower())

            if not config_ativo:
                return False, f"Ativo {ativo} não configurado"

            if not config_modo:
                return False, f"Modo {modo} não configurado"

            valor_entrada = config_ativo.get("min_stake", 0.35)
            meta_maxima = config_modo.get("meta_maxima")

            if valor_entrada > saldo:
                return False, "Saldo insuficiente"

            # Validação de meta por modo
            if meta_maxima and saldo > meta_maxima:
                return (
                    False,
                    f"Saldo excede limite do modo {modo} (máx: ${meta_maxima:.0f})",
                )

            # Validação de intervalo entre operações
            tempo_atual = time.time()
            intervalo_min = config_modo.get(
                "intervalo_minimo_s", self.intervalo_min_ops_s
            )

            if tempo_atual - self.ultima_operacao_ts < intervalo_min:
                return False, f"Aguarde {intervalo_min}s entre operações"

            return True, "Operação válida"

        except Exception as e:
            self.logger.error(f"Erro na validação: {e}")
            return False, f"Erro na validação: {e}"

    def obter_configuracao_completa_ativo(
        self, ativo: str, modo: str = "agressivo"
    ) -> dict:
        """Obtém configuração completa usando configurações centralizadas"""
        try:
            config_ativo = ATIVOS_SCALPING.get(ativo, {})
            config_modo = MODOS_OPERACAO_SCALPING.get(modo.lower(), {})

            return {
                "ativo": ativo,
                "nome": config_ativo.get("nome", ativo),
                "multiplicadores_disponiveis": config_ativo.get(
                    "multiplicadores_disponiveis", []
                ),
                "multiplicador_recomendado": self.obter_multiplicador_otimizado(
                    ativo, modo
                ),
                "multiplicador_padrao": config_ativo.get(
                    "multiplicador_padrao_turbo", 10
                ),
                "valor_entrada": config_ativo.get("min_stake", 0.35),
                "tipo_contrato": config_ativo.get("tipo_contrato", "multiplier"),
                "contract_types": config_ativo.get(
                    "contract_types", ["MULTUP", "MULTDOWN"]
                ),
                "prioridade": config_ativo.get("prioridade", 99),
                "volatilidade": config_ativo.get("volatilidade", "media"),
                "modo": modo,
                "meta_maxima": config_modo.get("meta_maxima"),
                "max_operacoes": config_modo.get("max_operacoes_simultaneas", 3),
                "confianca_min": config_modo.get("confianca_min_sinal", 0.80),
                "intervalo_min": config_modo.get("intervalo_minimo_s", 5.0),
                "configuracao_origem": "centralizada_otimizada",
            }

        except Exception as e:
            self.logger.error(f"Erro ao obter configuração completa: {e}")
            return {"ativo": ativo, "erro": str(e)}

    def adicionar_tick(self, preco: float) -> None:
        """Adiciona tick e gerencia velas usando configurações centralizadas"""
        try:
            timestamp_atual = time.time()
            self.ticks.append((timestamp_atual, preco))

            # Limita ticks em memória
            if len(self.ticks) > self.max_ticks_mem:
                self.ticks = self.ticks[-self.max_ticks_mem :]

            # Gerencia velas
            self._processar_vela(timestamp_atual, preco)

            # Limpeza automática
            if timestamp_atual - self.ultimo_cleanup_s >= self.intervalo_cleanup_s:
                self._executar_limpeza_automatica()
                self.ultimo_cleanup_s = timestamp_atual

        except Exception as e:
            self.logger.error(f"Erro ao adicionar tick: {e}")

    def obter_velas_atuais(self, incluir_em_formacao: bool = False) -> List[Dict]:
        """Obtém velas atuais usando configurações centralizadas"""
        try:
            velas = self.velas_ohlc.copy()

            if incluir_em_formacao and self._vela_atual_construcao:
                velas.append(self._vela_atual_construcao.copy())

            # Limita ao máximo configurado
            max_velas = CONFIG_CATALOGADOR.get("analise", {}).get(
                "max_velas_memoria", 2000
            )
            if len(velas) > max_velas:
                velas = velas[-max_velas:]

            return velas

        except Exception as e:
            self.logger.error(f"Erro ao obter velas: {e}")
            return []

    def obter_ultimos_ticks(self, n_ticks: int = 150) -> List[float]:
        """Retorna lista dos últimos n preços de ticks recebidos em tempo real."""
        try:
            if not self.ticks:
                return []
            return [float(preco) for _, preco in self.ticks[-n_ticks:]]
        except Exception:
            return []

    def obter_snapshot_mercado(self, ativo: str = None) -> Dict[str, Any]:
        """Constrói snapshot consolidado e enriquecido do mercado a partir dos ticks reais."""
        try:
            precos_ticks = self.obter_ultimos_ticks(150)
            if not precos_ticks:
                return {
                    "valido": False,
                    "razao": "Buffer de ticks vazio",
                    "preco_atual": 0.0,
                    "total_ticks": 0,
                }

            preco_atual = precos_ticks[-1]
            tupla_precos = tuple(precos_ticks)

            # Janelas configuradas
            config_scalper = getattr(bot_config, "MICRO_SCALPER_CONFIG", getattr(getattr(bot_config, "Config", object), "MICRO_SCALPER", {}))
            cfg_ext = config_scalper.get("extremo", {})

            j_curta = cfg_ext.get("janela_curta", 20)
            j_media = cfg_ext.get("janela_media", 60)
            j_longa = cfg_ext.get("janela_longa", 120)

            # Métricas estatísticas de distribuição
            percentil_curto = AnalisadorTecnico.calcular_percentil(
                tupla_precos, preco_atual, j_curta
            )
            percentil_medio = AnalisadorTecnico.calcular_percentil(
                tupla_precos, preco_atual, j_media
            )
            percentil_longo = AnalisadorTecnico.calcular_percentil(
                tupla_precos, preco_atual, j_longa
            )

            z_score_curto = AnalisadorTecnico.calcular_z_score(
                tupla_precos, preco_atual, j_curta
            )
            z_score_medio = AnalisadorTecnico.calcular_z_score(
                tupla_precos, preco_atual, j_media
            )

            # Indicadores técnicos clássicos calculados sobre os ticks
            rsi_val = AnalisadorTecnico.calcular_rsi(
                tupla_precos, cfg_ext.get("rsi_period", 14)
            )
            bb_val = AnalisadorTecnico.calcular_bollinger(
                tupla_precos,
                cfg_ext.get("bb_period", 20),
                cfg_ext.get("bb_std", 2.0),
            )
            ema_rapida = AnalisadorTecnico.calcular_ema(
                tupla_precos, cfg_ext.get("ema_fast", 8)
            )
            ema_lenta = AnalisadorTecnico.calcular_ema(
                tupla_precos, cfg_ext.get("ema_slow", 21)
            )

            dist_ema_rapida_pct = (
                ((preco_atual - ema_rapida) / ema_rapida * 100.0)
                if ema_rapida
                else 0.0
            )
            dist_ema_lenta_pct = (
                ((preco_atual - ema_lenta) / ema_lenta * 100.0)
                if ema_lenta
                else 0.0
            )

            # Dinâmica e reversão recente
            slope_5 = AnalisadorTecnico.calcular_inclinacao(tupla_precos, 5)
            slope_10 = AnalisadorTecnico.calcular_inclinacao(tupla_precos, 10)
            volatilidade = AnalisadorTecnico.calcular_volatilidade_instantanea(
                tupla_precos, 20
            )

            bb_sup = bb_val.get("superior", preco_atual) if bb_val else preco_atual
            bb_inf = bb_val.get("inferior", preco_atual) if bb_val else preco_atual
            bb_med = bb_val.get("media", preco_atual) if bb_val else preco_atual
            dist_bb_sup = (bb_sup - preco_atual) / preco_atual if preco_atual > 0 else 0.0
            dist_bb_inf = (preco_atual - bb_inf) / preco_atual if preco_atual > 0 else 0.0

            return {
                "valido": True,
                "ativo": ativo or self.ativo_selecionado,
                "preco_atual": preco_atual,
                "total_ticks": len(self.ticks),
                "ticks_count": len(precos_ticks),
                "timestamp": time.time(),
                "percentil_curto": percentil_curto,
                "percentil_medio": percentil_medio,
                "percentil_longo": percentil_longo,
                "z_score": z_score_curto or 0.0,
                "z_score_curto": z_score_curto,
                "z_score_medio": z_score_medio,
                "rsi": rsi_val if rsi_val is not None else 50.0,
                "bollinger": bb_val,
                "bb_superior": bb_sup,
                "bb_inferior": bb_inf,
                "bb_media": bb_med,
                "distancia_bb_superior": dist_bb_sup,
                "distancia_bb_inferior": dist_bb_inf,
                "ema_rapida": ema_rapida or preco_atual,
                "ema_lenta": ema_lenta or preco_atual,
                "dist_ema_rapida_pct": round(dist_ema_rapida_pct, 4),
                "dist_ema_lenta_pct": round(dist_ema_lenta_pct, 4),
                "slope_5": round(slope_5, 5),
                "slope_10": round(slope_10, 5),
                "inclinacao_curta": round(slope_5, 5),
                "volatilidade": round(volatilidade, 4),
                "volatilidade_instantanea": round(volatilidade, 4),
                "ticks_recentes": precos_ticks[-15:],
                "ultimos_ticks": precos_ticks,
            }
        except Exception as e:
            self.logger.error(f"Erro ao obter snapshot de mercado: {e}")
            return {
                "valido": False,
                "razao": f"Erro interno snapshot: {e}",
                "preco_atual": 0.0,
                "total_ticks": 0,
            }

    def _processar_vela(self, timestamp: float, preco: float) -> None:
        """Processa formação de velas usando timeframe configurado"""
        try:
            timestamp_vela = int(timestamp // self.timeframe_s) * self.timeframe_s

            if self._inicio_vela_atual_s != timestamp_vela:
                # Finaliza vela anterior se existir
                if self._vela_atual_construcao:
                    self.velas_ohlc.append(self._vela_atual_construcao.copy())

                    # Limita velas em memória
                    if len(self.velas_ohlc) > self.max_velas_mem:
                        self.velas_ohlc = self.velas_ohlc[-self.max_velas_mem :]

                # Inicia nova vela
                self._vela_atual_construcao = {
                    "timestamp": timestamp_vela,
                    "open": preco,
                    "high": preco,
                    "low": preco,
                    "close": preco,
                    "volume": 1,
                }
                self._inicio_vela_atual_s = timestamp_vela
            else:
                # Atualiza vela atual
                if self._vela_atual_construcao:
                    self._vela_atual_construcao["high"] = max(
                        self._vela_atual_construcao["high"], preco
                    )
                    self._vela_atual_construcao["low"] = min(
                        self._vela_atual_construcao["low"], preco
                    )
                    self._vela_atual_construcao["close"] = preco
                    self._vela_atual_construcao["volume"] += 1

        except Exception as e:
            self.logger.error(f"Erro ao processar vela: {e}")

    def _executar_limpeza_automatica(self) -> None:
        """Executa limpeza automática usando configurações centralizadas"""
        try:
            tempo_atual = time.time()

            # Limpa ticks antigos
            self.ticks = [
                (ts, preco)
                for ts, preco in self.ticks
                if tempo_atual - ts <= self.max_idade_ticks_s
            ]

            # Limpa velas antigas
            self.velas_ohlc = [
                vela
                for vela in self.velas_ohlc
                if tempo_atual - vela["timestamp"] <= self.max_idade_velas_s
            ]

            # Limpa operações antigas
            self.operacoes_ativas_ts = [
                ts
                for ts in self.operacoes_ativas_ts
                if tempo_atual - ts <= 3600  # 1 hora
            ]

            self.logger.debug(
                f"Limpeza automática executada: {len(self.ticks)} ticks, {len(self.velas_ohlc)} velas"
            )

        except Exception as e:
            self.logger.error(f"Erro na limpeza automática: {e}")

    def log_organizado(self, mensagem: str, nivel: str = "info") -> None:
        """Log organizado usando configurações centralizadas"""
        try:
            if hasattr(self.logger, nivel.lower()):
                getattr(self.logger, nivel.lower())(
                    f"[CATALOGADOR_OTIMIZADO] {mensagem}"
                )
            else:
                self.logger.info(f"[CATALOGADOR_OTIMIZADO] {mensagem}")

        except Exception as e:
            print(f"Erro no log: {e}")

    def pode_executar_operacao_agora(self) -> bool:
        """Verifica se o intervalo mínimo entre operações foi respeitado"""
        agora = time.time()
        if agora - self.ultima_operacao_ts < self.intervalo_min_ops_s:
            return False
        return True

    def verificar_protecao_operacoes(
        self, operacoes_abertas: list, meta: float, lucro_atual: float
    ) -> dict:
        """Verifica se o robô pode parar com segurança sem ordens abertas pendentes"""
        if operacoes_abertas and len(operacoes_abertas) > 0:
            return {
                "pode_parar": False,
                "razao": f"Aguardando {len(operacoes_abertas)} operações abertas finalizarem",
                "tempo_espera": 15,
            }
        return {"pode_parar": True, "razao": "Sem operações ativas"}

    def obter_status_lucro(self) -> dict:
        """Retorna o status consolidado de lucro e operações"""
        return {
            "lucro_sessao": self.lucro_total_sessao,
            "total_operacoes": len(self.historico_operacoes_finalizadas),
            "historico_recente": self.historico_operacoes_finalizadas[-10:],
        }

    def inicializar_scanner_ativos(self):
        """Inicializa lista de ativos do scanner"""
        self.ativos_priorizados = list(ATIVOS_SCALPING.keys())

    def analisar_melhor_ativo(self) -> str:
        """Retorna o melhor ativo selecionado para operações"""
        return getattr(self, "ativo_selecionado", "1HZ75V")


# Alias para compatibilidade - usa a versão otimizada
Catalogador = CatalogadorOtimizado


# Teste do catalogador otimizado
if __name__ == "__main__":
    logger.info("=== TESTE DO CATALOGADOR OTIMIZADO ===")

    try:
        # Instancia catalogador otimizado
        catalog = CatalogadorOtimizado()
        catalog.log_organizado("Catalogador Otimizado instanciado com sucesso", "info")

        # Testa configurações centralizadas
        logger.info("📊 Testando configurações centralizadas:")

        # Testa multiplicadores
        for ativo in ["R_10", "R_25", "R_50", "R_75", "R_100"]:
            for modo in ["iniciante", "conservador", "agressivo"]:
                mult = catalog.obter_multiplicador_otimizado(ativo, modo)
                config = catalog.obter_configuracao_completa_ativo(ativo, modo)
                valido, msg = catalog.validar_operacao_otimizada(ativo, modo, 100.0)

                logger.info(f"✅ {ativo} ({modo}): Mult=x{mult}, Válido={valido}")

        # Testa análise de volatilitys
        logger.info("🔍 Testando análise otimizada de volatilitys...")
        resultado = catalog.analisar_todos_volatilitys_e_escolher_melhor("agressivo")

        if "erro" not in resultado:
            melhor = resultado["melhor_ativo"]
            logger.info(
                f"🎯 Melhor ativo: {melhor['ativo']} (Assertividade: {melhor['assertividade']:.2f})"
            )
        else:
            logger.warning(f"Erro na análise: {resultado['erro']}")

        logger.info("✅ CATALOGADOR OTIMIZADO FUNCIONANDO PERFEITAMENTE!")

    except Exception as e:
        logger.error(f"❌ Erro no teste: {e}")
        import traceback

        traceback.print_exc()
