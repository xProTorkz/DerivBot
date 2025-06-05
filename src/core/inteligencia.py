import json
import os
import numpy as np
import pandas as pd  # Keep pandas for Inteligencia class
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta  # Keep datetime
import logging
from cachetools import TTLCache

# Importa as configurações centralizadas
from src import (
    config as global_config,
)  # Use an alias to avoid conflict with local 'config' variables

# Diretório para armazenar os dados de memória
MEMORIA_DIR = "memoria_inteligencia"  # Renamed to avoid conflict if catalogador also uses "memoria"

# Setup logger for this module
logger_intel = logging.getLogger("inteligencia")  # Use a specific logger


def _criar_diretorio_memoria():
    if not os.path.exists(MEMORIA_DIR):
        os.makedirs(MEMORIA_DIR)


def _obter_arquivo_memoria(cliente_id: str) -> str:
    return os.path.join(
        MEMORIA_DIR, f"{cliente_id}_intel_data.json"
    )  # Changed filename


def carregar_memoria(cliente_id: str) -> Dict[str, Any]:
    try:
        _criar_diretorio_memoria()
        arquivo = _obter_arquivo_memoria(cliente_id)
        if not os.path.exists(arquivo):
            return {
                "historico": [],
                "ultima_atualizacao": datetime.now().isoformat(),
                "estatisticas": {
                    "total_operacoes": 0,
                    "lucro_total": 0.0,
                    "assertividade": 0.0,
                },
            }
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger_intel.error(f"Erro ao carregar memória IA para {cliente_id}: {e}")
        return {
            "historico": [],
            "ultima_atualizacao": datetime.now().isoformat(),
            "estatisticas": {
                "total_operacoes": 0,
                "lucro_total": 0.0,
                "assertividade": 0.0,
            },
        }


def salvar_memoria(
    cliente_id: str, dados_nova_operacao: Dict[str, Any]
) -> bool:  # Changed 'dados' to 'dados_nova_operacao'
    try:
        _criar_diretorio_memoria()
        arquivo = _obter_arquivo_memoria(cliente_id)
        dados_existentes = carregar_memoria(cliente_id)

        # Adiciona a nova operação ao histórico
        dados_existentes["historico"].append(
            dados_nova_operacao
        )  # Append the new operation data
        dados_existentes["ultima_atualizacao"] = datetime.now().isoformat()

        historico = dados_existentes["historico"]
        total_ops = len(historico)
        lucro_total = sum(
            float(op.get("lucro", 0.0)) for op in historico
        )  # Ensure float
        ops_lucro = sum(1 for op in historico if float(op.get("lucro", 0.0)) > 0)

        dados_existentes["estatisticas"] = {
            "total_operacoes": total_ops,
            "lucro_total": lucro_total,
            "assertividade": (
                (ops_lucro / total_ops * 100) if total_ops > 0 else 0.0
            ),  # Ensure float
        }
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(dados_existentes, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger_intel.error(f"Erro ao salvar memória IA para {cliente_id}: {e}")
        return False


def limpar_memoria(cliente_id: str) -> bool:
    try:
        arquivo = _obter_arquivo_memoria(cliente_id)
        if os.path.exists(arquivo):
            os.remove(arquivo)
        logger_intel.info(f"Memória IA para cliente {cliente_id} limpa.")
        return True
    except Exception as e:
        logger_intel.error(f"Erro ao limpar memória IA para {cliente_id}: {e}")
        return False


# =================== FUNÇÕES PARA SUPORTE E RESISTÊNCIA ===================
def detectar_suporte_resistencia(
    velas: List[Dict],
    janela: int = global_config.CONFIG_MICRO_SCALPING_ANALISE[
        "suporte_resistencia_janela_velas"
    ],
) -> Tuple[List[float], List[float]]:
    try:
        if len(velas) < janela * 2 + 1:
            return [], []  # Need enough data points

        # Using 'low' for support and 'high' for resistance detection more accurately
        lows = pd.Series([v["low"] for v in velas])
        highs = pd.Series([v["high"] for v in velas])

        # Find local minima (support) and maxima (resistance) using rolling windows
        # A point is a local min if it's the minimum in a window around it
        suportes_indices = lows[
            (lows.rolling(window=2 * janela + 1, center=True).min() == lows)
        ].index
        resistencias_indices = highs[
            (highs.rolling(window=2 * janela + 1, center=True).max() == highs)
        ].index

        suportes = [
            lows[i] for i in suportes_indices if i < len(lows)
        ]  # Ensure index is valid
        resistencias = [
            highs[i] for i in resistencias_indices if i < len(highs)
        ]  # Ensure index is valid

        if suportes:
            suportes = agrupar_niveis_proximos(
                suportes,
                global_config.CONFIG_MICRO_SCALPING_ANALISE[
                    "suporte_resistencia_margem_percent"
                ],
            )
        if resistencias:
            resistencias = agrupar_niveis_proximos(
                resistencias,
                global_config.CONFIG_MICRO_SCALPING_ANALISE[
                    "suporte_resistencia_margem_percent"
                ],
            )

        return sorted(list(set(suportes))), sorted(list(set(resistencias)))
    except Exception as e:
        logger_intel.error(f"Erro ao detectar S/R: {e}", exc_info=True)
        return [], []


def agrupar_niveis_proximos(
    niveis: List[float], threshold_percent: float  # No default, use from global_config
) -> List[float]:
    if not niveis:
        return []
    niveis_ordenados = sorted(list(set(niveis)))  # Remove duplicates before grouping
    if not niveis_ordenados:
        return []

    niveis_agrupados = []
    grupo_atual = [niveis_ordenados[0]]

    for i in range(1, len(niveis_ordenados)):
        nivel_atual = niveis_ordenados[i]
        media_grupo = sum(grupo_atual) / len(
            grupo_atual
        )  # Compare with current group's average

        # Check if nivel_atual is close to media_grupo
        if media_grupo == 0 and nivel_atual == 0:  # Both zero
            diff_percent = 0.0
        elif (
            media_grupo == 0
        ):  # Avoid division by zero if media_grupo is zero but nivel_atual is not
            diff_percent = float("inf")  # Consider them not part of the same group
        else:
            diff_percent = abs(nivel_atual - media_grupo) / media_grupo

        if diff_percent <= threshold_percent:
            grupo_atual.append(nivel_atual)
        else:
            niveis_agrupados.append(sum(grupo_atual) / len(grupo_atual))
            grupo_atual = [nivel_atual]
    if grupo_atual:
        niveis_agrupados.append(sum(grupo_atual) / len(grupo_atual))
    return sorted(list(set(niveis_agrupados)))


def esta_em_suporte_ou_resistencia(  # Combined function for efficiency
    preco_atual: float, niveis: List[float], margem_percent: float  # No default
) -> bool:
    if not niveis:
        return False
    for nivel in niveis:
        if nivel == 0 and preco_atual == 0:
            margem = 0  # handle both zero case
        elif nivel == 0:
            margem = (
                preco_atual * margem_percent
            )  # if nivel is 0, use preco_atual for margem
        else:
            margem = nivel * margem_percent

        if abs(preco_atual - nivel) <= margem:
            return True
    return False


def calcular_rsi_local(
    precos: List[float], periodo: int = global_config.RSI_PERIODO_PADRAO
) -> float:
    """Calcula o Índice de Força Relativa (RSI) localmente, usando config."""
    # This is a simplified RSI calculation, can be replaced by a more robust one from catalogador.AnalisadorTecnico
    # if circular dependencies are managed or if AnalisadorTecnico is moved to a shared utils module.
    if len(precos) < periodo + 1:
        return 50.0
    deltas = np.diff(precos)
    seed = deltas[:periodo]  # Use only first 'periodo' deltas for initial SMMA

    gains = np.maximum(seed, 0)
    losses = np.maximum(-seed, 0)

    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)

    # SMMA for subsequent values
    for i in range(periodo, len(deltas)):
        delta = deltas[i]
        avg_gain = (avg_gain * (periodo - 1) + max(delta, 0)) / periodo
        avg_loss = (avg_loss * (periodo - 1) + max(-delta, 0)) / periodo

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def analisar_micro_scalping(
    velas: List[Dict],
    meta: float,
    lucro_atual: float,
    modo: str,
    operacoes_ativas: int = 0,
) -> Dict[str, Any]:
    try:
        if (
            len(velas)
            < global_config.CONFIG_ANALISE_CATALOGADOR["limites"]["min_velas_analise"]
        ):  # Use min_velas from config
            return {
                "sinal": None,
                "confianca": 0.0,
                "razao": "Dados de velas insuficientes",
            }

        modo_config = global_config.MODOS_OPERACAO_SCALPING.get(
            modo, global_config.MODOS_OPERACAO_SCALPING["iniciante"]
        )
        max_operacoes_simultaneas = modo_config["max_operacoes_simultaneas"]

        if operacoes_ativas >= max_operacoes_simultaneas:
            return {
                "sinal": None,
                "confianca": 0.0,
                "razao": f"Máximo de operações ({operacoes_ativas}/{max_operacoes_simultaneas})",
            }

        # Meta progress check (original logic)
        meta_atingida_percent = (lucro_atual / meta * 100) if meta > 0 else 0
        if (
            meta_atingida_percent
            > global_config.CONFIG_MICRO_SCALPING_ANALISE[
                "meta_progresso_reducao_ops_percent"
            ]
        ):
            reducao_fator = (100.0 - meta_atingida_percent) / (
                100.0
                - global_config.CONFIG_MICRO_SCALPING_ANALISE[
                    "meta_progresso_reducao_ops_percent"
                ]
            )
            max_ops_reduzido = max(1, int(max_operacoes_simultaneas * reducao_fator))
            if operacoes_ativas >= max_ops_reduzido:
                return {
                    "sinal": None,
                    "confianca": 0.0,
                    "razao": f"Próximo da meta ({meta_atingida_percent:.1f}%). Ops limitadas a {max_ops_reduzido}",
                }

        closes = [v["close"] for v in velas]
        # RSI from local calculation or preferably from a shared AnalisadorTecnico
        rsi_period = global_config.CONFIG_ESTRATEGIA_TURBO["indicadores"]["rsi_periodo"]
        rsi = calcular_rsi_local(closes, periodo=rsi_period)

        suportes, resistencias = detectar_suporte_resistencia(velas)
        preco_atual = velas[-1]["close"]

        # Simplified direction: last 3 candles
        if len(velas) >= 3:
            direcao_curta = (
                "ALTA"
                if velas[-1]["close"] > velas[-3]["close"]
                else ("BAIXA" if velas[-1]["close"] < velas[-3]["close"] else "NEUTRA")
            )
        else:
            direcao_curta = "NEUTRA"

        # Volatility: Standard deviation of last 10 closes
        volatilidade = np.std(closes[-10:]) if len(closes) >= 10 else 0.0

        # Força da tendência: (preco_atual - preco_5_velas_atras) / preco_5_velas_atras
        if len(closes) >= 5 and closes[-5] != 0:
            forca_tendencia = abs(closes[-1] - closes[-5]) / closes[-5] * 100
        else:
            forca_tendencia = 0.0

        decisao = None
        confianca = 0.0
        razao = "Aguardando"

        conf_min_modo = modo_config["confianca_min_sinal"]
        rsi_sobrecompra_lim = global_config.CONFIG_MICRO_SCALPING_ANALISE[
            "rsi_sobrecompra_limiar"
        ]
        rsi_sobrevenda_lim = global_config.CONFIG_MICRO_SCALPING_ANALISE[
            "rsi_sobrevenda_limiar"
        ]
        margem_sr = global_config.CONFIG_MICRO_SCALPING_ANALISE[
            "suporte_resistencia_margem_percent"
        ]

        # Lógica de Decisão (simplificada para exemplo, pode ser mais complexa)
        if (
            esta_em_suporte_ou_resistencia(preco_atual, resistencias, margem_sr)
            and rsi > rsi_sobrecompra_lim
        ):
            decisao = "venda"
            confianca = 0.70 + (rsi - rsi_sobrecompra_lim) / 100.0  # Base + rsi factor
            razao = f"Resistência ({preco_atual:.5f}) + RSI Sobrecomprado ({rsi:.1f})"
        elif (
            esta_em_suporte_ou_resistencia(preco_atual, suportes, margem_sr)
            and rsi < rsi_sobrevenda_lim
        ):
            decisao = "compra"
            confianca = 0.70 + (rsi_sobrevenda_lim - rsi) / 100.0
            razao = f"Suporte ({preco_atual:.5f}) + RSI Sobrevendido ({rsi:.1f})"

        # Adicionar lógica de tendência se não houver sinal de S/R forte
        elif decisao is None:
            if (
                direcao_curta == "ALTA"
                and forca_tendencia > 0.05
                and rsi > 50
                and rsi < rsi_sobrecompra_lim - 5
            ):  # Ex: 0.05% de força, RSI não extremo
                decisao = "compra"
                confianca = 0.60 + forca_tendencia * 10  # Confiança baseada na força
                razao = f"Tendência de Alta ({direcao_curta}), Força: {forca_tendencia:.3f}%, RSI: {rsi:.1f}"
            elif (
                direcao_curta == "BAIXA"
                and forca_tendencia > 0.05
                and rsi < 50
                and rsi > rsi_sobrevenda_lim + 5
            ):
                decisao = "venda"
                confianca = 0.60 + forca_tendencia * 10
                razao = f"Tendência de Baixa ({direcao_curta}), Força: {forca_tendencia:.3f}%, RSI: {rsi:.1f}"

        if decisao and confianca < conf_min_modo:
            razao += f" (Conf {confianca:.2f} < Min {conf_min_modo} - Aguardando)"
            decisao = None
            confianca = 0.0

        confianca = min(confianca, 0.99)  # Cap confidence

        return {
            "sinal": decisao,
            "confianca": round(confianca, 2),
            "razao": razao,
            "analise": {
                "preco": preco_atual,
                "rsi": round(rsi, 1),
                "direcao": direcao_curta,
                "forca_tendencia": round(forca_tendencia, 3),
                "volatilidade": round(volatilidade, 5),
                "suportes": suportes[-3:],
                "resistencias": resistencias[-3:],
                "meta_progresso_percent": round(meta_atingida_percent, 1),
            },
        }
    except Exception as e:
        logger_intel.error(f"Erro na análise de micro scalping: {e}", exc_info=True)
        return {"sinal": None, "confianca": 0.0, "razao": f"Erro: {str(e)}"}


# Classe Inteligencia (mais geral, baseada em pandas)
class Inteligencia:
    def __init__(self):
        self.logger = logging.getLogger("InteligenciaClasse")  # Different logger name
        self.cache: Dict[str, Any] = {}  # Initialize cache
        self.ultima_analise: Optional[Dict] = None  # Initialize ultima_analise

    def analisar_mercado(self, dados_velas: List[Dict]) -> Dict:
        try:
            if (
                not dados_velas
                or len(dados_velas) < global_config.BOLLINGER_PERIODO_PADRAO
            ):  # Need enough for longest indicator
                return {
                    "direcao": "neutro",
                    "confianca": 0.0,
                    "indicadores": {},
                    "razao": "Dados insuficientes",
                }
            df = pd.DataFrame(dados_velas)
            if not all(col in df.columns for col in ["open", "high", "low", "close"]):
                return {
                    "direcao": "neutro",
                    "confianca": 0.0,
                    "indicadores": {},
                    "razao": "Colunas OHLC ausentes",
                }

            indicadores = self._calcular_indicadores(df)
            previsao = self._gerar_previsao(
                df["close"].iloc[-1], indicadores
            )  # Pass current price for BB check

            self.ultima_analise = {
                "timestamp": datetime.now().isoformat(),
                "indicadores": indicadores,
                "previsao": previsao,
            }
            self.cache["ultima_analise"] = (
                self.ultima_analise
            )  # Store in instance cache
            return previsao
        except Exception as e:
            self.logger.error(
                f"Erro na análise de mercado (Inteligencia): {str(e)}", exc_info=True
            )
            return {
                "direcao": "neutro",
                "confianca": 0.0,
                "indicadores": {},
                "razao": f"Erro: {str(e)}",
            }

    def _calcular_indicadores(self, df: pd.DataFrame) -> Dict:
        indicadores = {}
        closes = df["close"]  # Use Series for direct indicator calculation

        # RSI
        rsi_period = global_config.RSI_PERIODO_PADRAO
        delta = closes.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(
            window=rsi_period, min_periods=1
        ).mean()  # Use rolling for pandas Series
        avg_loss = loss.rolling(window=rsi_period, min_periods=1).mean()
        rs = avg_gain / avg_loss
        indicadores["rsi"] = (100.0 - (100.0 / (1.0 + rs))).fillna(
            50.0
        )  # Handle NaN with 50

        # MACD
        exp1 = closes.ewm(span=12, adjust=False).mean()
        exp2 = closes.ewm(span=26, adjust=False).mean()
        indicadores["macd"] = exp1 - exp2
        indicadores["macd_signal"] = (
            indicadores["macd"].ewm(span=9, adjust=False).mean()
        )

        # Bollinger Bands
        bollinger_period = global_config.BOLLINGER_PERIODO_PADRAO
        bollinger_dev = global_config.BOLLINGER_DESVIO_PADRAO
        sma_bb = closes.rolling(window=bollinger_period).mean()
        std_bb = closes.rolling(window=bollinger_period).std()
        indicadores["bb_media"] = sma_bb  # Added BB media
        indicadores["bb_upper"] = sma_bb + (std_bb * bollinger_dev)
        indicadores["bb_lower"] = sma_bb - (std_bb * bollinger_dev)

        # Moving Averages from config
        indicadores[f"sma_{global_config.EMA_RAPIDA_PADRAO}"] = closes.rolling(
            window=global_config.EMA_RAPIDA_PADRAO
        ).mean()
        indicadores[f"sma_{global_config.EMA_LENTA_PADRAO}"] = closes.rolling(
            window=global_config.EMA_LENTA_PADRAO
        ).mean()
        # indicadores["sma_200"] = closes.rolling(window=200).mean() # if 200 is needed

        # Return last value of each indicator
        # Ensure all indicators have a value (e.g., by using .iloc[-1] and handling potential NaNs)
        final_indicadores = {}
        for key, series in indicadores.items():
            if not series.empty:
                final_indicadores[key] = (
                    series.iloc[-1] if pd.notna(series.iloc[-1]) else None
                )
            else:
                final_indicadores[key] = None
        return final_indicadores

    def _gerar_previsao(self, preco_atual: float, indicadores: Dict) -> Dict:
        sinais_compra = 0
        sinais_venda = 0
        total_sinais_validos = 0

        # RSI
        rsi = indicadores.get("rsi")
        if rsi is not None:
            total_sinais_validos += 1
            if rsi < global_config.RSI_SOBREVENDIDO_PADRAO:
                sinais_compra += 1
            elif rsi > global_config.RSI_SOBRECOMPRADO_PADRAO:
                sinais_venda += 1

        # MACD
        macd = indicadores.get("macd")
        signal = indicadores.get("macd_signal")
        if macd is not None and signal is not None:
            total_sinais_validos += 1
            if macd > signal:
                sinais_compra += 1
            elif macd < signal:
                sinais_venda += 1

        # Bollinger Bands
        bb_upper = indicadores.get("bb_upper")
        bb_lower = indicadores.get("bb_lower")
        if bb_upper is not None and bb_lower is not None and preco_atual is not None:
            total_sinais_validos += 1
            if preco_atual < bb_lower:
                sinais_compra += 1
            elif preco_atual > bb_upper:
                sinais_venda += 1

        # Moving Averages (EMA_RAPIDA_PADRAO as short, EMA_LENTA_PADRAO as long)
        sma_curta_key = f"sma_{global_config.EMA_RAPIDA_PADRAO}"
        sma_longa_key = f"sma_{global_config.EMA_LENTA_PADRAO}"
        sma_curta = indicadores.get(sma_curta_key)
        sma_longa = indicadores.get(sma_longa_key)

        if sma_curta is not None and sma_longa is not None:
            total_sinais_validos += 1
            if sma_curta > sma_longa:
                sinais_compra += 1
            elif sma_curta < sma_longa:
                sinais_venda += 1

        direcao = "neutro"
        confianca = 0.0
        if total_sinais_validos > 0:
            if sinais_compra > sinais_venda:
                direcao = "compra"
                confianca = sinais_compra / total_sinais_validos
            elif sinais_venda > sinais_compra:
                direcao = "venda"
                confianca = sinais_venda / total_sinais_validos
            else:  # sinais_compra == sinais_venda
                confianca = 0.5  # Neutral confidence if signals are balanced

        # Clean up indicators dict for JSON (remove NaN)
        final_indicadores_dict = {
            k: (
                round(v, 5)
                if isinstance(v, (float, np.floating)) and pd.notna(v)
                else None
            )
            for k, v in indicadores.items()
        }

        return {
            "direcao": direcao,
            "confianca": round(confianca, 2),
            "indicadores": final_indicadores_dict,
        }

    def get_ultima_analise(self) -> Optional[Dict]:
        return self.cache.get("ultima_analise")

    def limpar_cache(self):
        self.cache = {}
        self.ultima_analise = None


# Instância global (opcional, pode ser gerenciada externamente)
# inteligencia_global = Inteligencia()


class AnaliseTecnica:
    def __init__(self):
        self.indicadores_cache = TTLCache(maxsize=100, ttl=1)

    def decidir_modo_operacao(self, dados: dict) -> str:
        """Decisão de modo com critérios melhorados"""
        try:
            volatilidade = self.calcular_volatilidade(dados)
            tendencia = self.calcular_tendencia(dados)
            volume = self.calcular_volume(dados)

            # Critérios para Multiplier
            if volatilidade > 0.4 and volume > 1000 and self.spread_adequado(dados):
                return "multiplier"

            # Critérios para Turbo
            if tendencia > 0.7 and dados["payout"] >= 85 and volatilidade <= 0.3:
                return "turbo"

            return "aguardar"

        except Exception as e:
            self.logger.error(f"Erro na decisão: {e}")
            return "aguardar"
