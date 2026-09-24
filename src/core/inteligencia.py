import json
import os
import time
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

try:
    from src.config.config import obter_limite_posicoes
except ImportError:
    try:
        from config.config import obter_limite_posicoes
    except ImportError:
        def obter_limite_posicoes(m: Optional[str] = None) -> int:
            limits = {"iniciante": 3, "intermediario": 5, "conservador": 5, "agressivo": 10}
            return limits.get(str(m).lower() if m else "iniciante", 3)

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


# ==============================================================================
# INTELIGÊNCIA MICRO-SCALPER EXTREMAMENTE SELETIVO (Issues #2, #3, #4)
# ==============================================================================

class MicroScalperState:
    NORMAL = "NORMAL"
    EXTREMO_DETECTADO = "EXTREMO_DETECTADO"
    AGUARDANDO_REVERSAO = "AGUARDANDO_REVERSAO"
    SINAL_CONFIRMADO = "SINAL_CONFIRMADO"
    VALIDANDO_RISCO = "VALIDANDO_RISCO"
    COMPRANDO = "COMPRANDO"
    POSICAO_ABERTA = "POSICAO_ABERTA"
    SAINDO = "SAINDO"
    COOLDOWN = "COOLDOWN"


class MarketRegime:
    """Classificação canônica de regime de mercado (Issue #17)."""
    REVERSAO_VALIDA = "REVERSAO_VALIDA"
    TENDENCIA_FORTE = "TENDENCIA_FORTE"
    CHOP = "CHOP"
    VOLATILIDADE_BAIXA = "VOLATILIDADE_BAIXA"
    VOLATILIDADE_ANORMAL = "VOLATILIDADE_ANORMAL"
    DADOS_STALE = "DADOS_STALE"
    NO_TRADE = "NO_TRADE"


class RegimeClassifier:
    """
    Classificador de Regime de Mercado (Issue #17).
    Determina se o mercado oferece vantagem estatística para entrada de reversão.
    Regra inviolável: se houver dúvida ou regime adverso -> NO_TRADE.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg_micro = getattr(global_config, "MICRO_SCALPER_CONFIG", {})
        self.config = config or cfg_micro.get("regime", {
            "adx_tendencia_forte": 32.0,
            "volatilidade_baixa_min": 0.00005,
            "volatilidade_anormal_max": 0.05,
        })

    def classificar(
        self,
        ativo: str,
        ticks: List[float],
        snapshot: Dict[str, Any],
        direcao_pretendida: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Classifica o regime atual do ativo e decide se autoriza operação.
        """
        if not ticks or len(ticks) < 10:
            return {
                "regime": MarketRegime.NO_TRADE,
                "aprovado": False,
                "razao": f"Ticks insuficientes para classificação de regime ({len(ticks) if ticks else 0}/10)",
                "detalhes": {},
            }

        preco_atual = float(ticks[-1])
        if preco_atual <= 0:
            return {
                "regime": MarketRegime.NO_TRADE,
                "aprovado": False,
                "razao": "Preço atual inválido (<= 0)",
                "detalhes": {},
            }

        # 1. Checagem de dados stale (idade do tick > 3.5s ou ticks estáticos duplicados)
        idade_tick = float(snapshot.get("idade_tick", 0.0) or snapshot.get("tempo_stale", 0.0))
        if idade_tick > 3.5:
            return {
                "regime": MarketRegime.DADOS_STALE,
                "aprovado": False,
                "razao": f"Dados stale detectados (idade do tick: {idade_tick:.1f}s > 3.5s)",
                "detalhes": {"idade_tick": idade_tick},
            }

        if len(ticks) >= 5 and len(set(ticks[-5:])) <= 1:
            return {
                "regime": MarketRegime.DADOS_STALE,
                "aprovado": False,
                "razao": "Dados estáticos detectados (últimos 5 ticks idênticos)",
                "detalhes": {"ticks_recentes": ticks[-5:]},
            }

        # 2. Volatilidade e desvio padrão dos últimos ticks
        n_ticks_vol = min(len(ticks), 20)
        std_ticks = float(np.std(ticks[-n_ticks_vol:])) if n_ticks_vol >= 5 else 0.0
        vol_rel = (std_ticks / preco_atual) if preco_atual > 0 else 0.0

        # Checagem de volatilidade baixa (mercado morto)
        vol_min = self.config.get("volatilidade_baixa_min", 0.00005)
        if std_ticks == 0.0 or vol_rel < vol_min:
            return {
                "regime": MarketRegime.VOLATILIDADE_BAIXA,
                "aprovado": False,
                "razao": f"Volatilidade insuficiente ({vol_rel:.6f} < {vol_min:.6f})",
                "detalhes": {"vol_rel": vol_rel, "std_ticks": std_ticks},
            }

        # Checagem de volatilidade anormal (gap gigante / spike atípico)
        vol_max = self.config.get("volatilidade_anormal_max", 0.05)
        ultimo_delta = abs(ticks[-1] - ticks[-2]) if len(ticks) >= 2 else 0.0
        if len(ticks) >= 10 and std_ticks > 0:
            if ultimo_delta > max(4.0 * std_ticks, preco_atual * 0.015) or vol_rel > vol_max:
                return {
                    "regime": MarketRegime.VOLATILIDADE_ANORMAL,
                    "aprovado": False,
                    "razao": f"Volatilidade anormal / spike ({ultimo_delta:.4f} > 4x std {std_ticks:.4f})",
                    "detalhes": {"ultimo_delta": ultimo_delta, "std_ticks": std_ticks},
                }

        # 3. Tendência Forte Contrária (bloqueio de faca caindo / foguete subindo)
        deltas = [ticks[i] - ticks[i - 1] for i in range(1, len(ticks))]
        ultimos_deltas = deltas[-6:] if len(deltas) >= 6 else deltas
        inclinacao_curta = float(snapshot.get("inclinacao_curta", 0.0))

        if direcao_pretendida == "CALL":
            # CALL tenta comprar fundo. Se mercado está em queda livre contínua:
            quedas_consecutivas = 0
            for d in reversed(ultimos_deltas):
                if d <= 0:
                    quedas_consecutivas += 1
                else:
                    break
            # Queda de 5+ ticks seguidos sem repique ou slope acelerando para baixo
            if quedas_consecutivas >= 5 or (quedas_consecutivas >= 4 and inclinacao_curta < -0.001 * preco_atual):
                return {
                    "regime": MarketRegime.TENDENCIA_FORTE,
                    "aprovado": False,
                    "razao": f"Tendência de baixa forte em andamento ({quedas_consecutivas} ticks de queda contínua, slope {inclinacao_curta:.4f})",
                    "detalhes": {"quedas_consecutivas": quedas_consecutivas, "slope": inclinacao_curta},
                }

        elif direcao_pretendida == "PUT":
            # PUT tenta vender topo. Se mercado está em alta forte contínua:
            altas_consecutivas = 0
            for d in reversed(ultimos_deltas):
                if d >= 0:
                    altas_consecutivas += 1
                else:
                    break
            # Alta de 5+ ticks seguidos sem recuo ou slope acelerando para cima
            if altas_consecutivas >= 5 or (altas_consecutivas >= 4 and inclinacao_curta > 0.001 * preco_atual):
                return {
                    "regime": MarketRegime.TENDENCIA_FORTE,
                    "aprovado": False,
                    "razao": f"Tendência de alta forte em andamento ({altas_consecutivas} ticks de alta contínua, slope {inclinacao_curta:.4f})",
                    "detalhes": {"altas_consecutivas": altas_consecutivas, "slope": inclinacao_curta},
                }

        # 4. CHOP (Ruído excessivo e micro-range comprimido)
        if len(deltas) >= 12:
            sign_flips = sum(1 for i in range(1, len(ultimos_deltas)) if (ultimos_deltas[i] * ultimos_deltas[i - 1]) < 0)
            deslocamento = abs(ticks[-1] - ticks[-12])
            if sign_flips >= 7 and deslocamento < 0.3 * std_ticks:
                return {
                    "regime": MarketRegime.CHOP,
                    "aprovado": False,
                    "razao": f"Mercado em chop/ruído excessivo ({sign_flips} inversões de sinal em 12 ticks)",
                    "detalhes": {"sign_flips": sign_flips, "deslocamento": deslocamento},
                }

        # 5. Se passou por todas as rejeições, temos uma Reversão Válida
        return {
            "regime": MarketRegime.REVERSAO_VALIDA,
            "aprovado": True,
            "razao": "Regime de reversão estatisticamente válido",
            "detalhes": {
                "std_ticks": std_ticks,
                "vol_rel": vol_rel,
                "slope": inclinacao_curta,
            },
        }


class Timing24Detector:
    """
    Detector determinístico de Timing 2/4 por ticks (Issue #13).
    Isolamento de estado rigoroso por ativo (CROSS_ASSET_TIMING_CONTAMINATION=0).
    Regras:
    - PUT: 2 picos superiores locais com recuo (pullback >= epsilon). Janela de 1 a 4 ticks.
    - CALL: 2 fundos inferiores locais com repique (bounce >= epsilon). Janela de 1 a 4 ticks.
    - Se confirmação ocorrer entre ticks 1 e 4: sinal aprovado.
    - Se tick > 4: TIMING_2_4_EXPIRED -> NO_TRADE.
    - Se preço romper extremo: CONTINUACAO_DE_TENDENCIA -> NO_TRADE.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg_micro = getattr(global_config, "MICRO_SCALPER_CONFIG", {})
        self.config = config or cfg_micro.get("timing_2_4", {
            "max_confirmation_window": 4,
            "min_peak_distance_ticks": 2,
            "max_peak_distance_ticks": 25,
            "epsilon_factor": 0.20,
        })
        self.estados_por_ativo: Dict[str, Dict[str, Any]] = {}

    def obter_estado(self, ativo: str) -> Dict[str, Any]:
        simbolo = str(ativo or "GLOBAL").upper().strip()
        if simbolo not in self.estados_por_ativo:
            self.estados_por_ativo[simbolo] = {
                "ativo": simbolo,
                "direction_candidate": None,
                "peak_count": 0,
                "peaks": [],
                "second_peak_tick_index": None,
                "confirmation_tick": None,
                "pattern_started_at": 0.0,
                "pattern_status": "IDLE",
                "last_rejection_reason": "",
                "last_telemetry": {},
            }
        return self.estados_por_ativo[simbolo]

    def resetar_estado(self, ativo: Optional[str] = None):
        if ativo:
            simbolo = str(ativo).upper().strip()
            if simbolo in self.estados_por_ativo:
                del self.estados_por_ativo[simbolo]
        else:
            self.estados_por_ativo.clear()

    def detectar(
        self,
        ativo: str,
        ticks: List[float],
        direcao_pretendida: str,
    ) -> Dict[str, Any]:
        """
        Analisa a sequência de ticks reais e detecta o padrão 2/4 determinístico.
        """
        simbolo = str(ativo or "GLOBAL").upper().strip()
        estado = self.obter_estado(simbolo)

        if not ticks or len(ticks) < 8:
            motivo = f"Buffer insuficiente para Timing 2/4 ({len(ticks) if ticks else 0}/8 ticks)"
            estado["pattern_status"] = "INSUFFICIENT_DATA"
            estado["last_rejection_reason"] = motivo
            return {
                "ativo": simbolo,
                "direcao": direcao_pretendida,
                "aprovado": False,
                "pattern_status": "INSUFFICIENT_DATA",
                "confirmation_tick": None,
                "picos_detectados": 0,
                "preco_pico_1": None,
                "preco_pico_2": None,
                "razao": motivo,
                "telemetria": {},
            }

        # Janela de análise dos últimos ticks
        janela = min(len(ticks), 30)
        serie = ticks[-janela:]
        n = len(serie)
        preco_atual = serie[-1]

        # Cálculo dinâmico do epsilon adaptado ao ativo e escala
        std_local = float(np.std(serie[-15:])) if len(serie) >= 15 else float(np.std(serie))
        fator_eps = float(self.config.get("epsilon_factor", 0.20))
        epsilon = max(std_local * fator_eps, preco_atual * 0.00005, 0.001)

        max_window = int(self.config.get("max_confirmation_window", 4))

        if direcao_pretendida == "PUT":
            # Busca dois picos superiores (máximos locais)
            # Um pico ocorre em i se serie[i] > serie[i-1] e serie[i] >= serie[i+1]
            picos_idx = []
            for i in range(1, n - 1):
                if serie[i] > serie[i - 1] and serie[i] >= serie[i + 1]:
                    if (serie[i] - min(serie[i - 1], serie[i + 1])) >= epsilon * 0.4:
                        picos_idx.append(i)

            if n >= 2 and serie[-1] > serie[-2] and (serie[-1] - serie[-2]) >= epsilon * 0.4:
                picos_idx.append(n - 1)

            if len(picos_idx) < 2:
                # Dois ticks consecutivos de alta NÃO contam como dois picos
                motivo = "Menos de 2 picos superiores confirmados"
                estado["pattern_status"] = "NO_TWO_PEAKS"
                estado["last_rejection_reason"] = motivo
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": False,
                    "pattern_status": "NO_TWO_PEAKS",
                    "confirmation_tick": None,
                    "picos_detectados": len(picos_idx),
                    "preco_pico_1": serie[picos_idx[0]] if picos_idx else None,
                    "preco_pico_2": None,
                    "razao": motivo,
                    "telemetria": {"epsilon": epsilon, "picos_idx": picos_idx},
                }

            # Encontra o par mais recente de picos com um vale intermediário >= epsilon
            par_valido = None
            for p2_cand in reversed(picos_idx):
                for p1_cand in reversed([p for p in picos_idx if p < p2_cand]):
                    vales_entre = [serie[j] for j in range(p1_cand + 1, p2_cand)]
                    if vales_entre:
                        min_vale = min(vales_entre)
                        recuo_p1 = serie[p1_cand] - min_vale
                        recuo_p2 = serie[p2_cand] - min_vale
                        if recuo_p1 >= epsilon and recuo_p2 >= epsilon:
                            par_valido = (p1_cand, p2_cand)
                            break
                if par_valido:
                    break

            if not par_valido:
                motivo = "Dois picos detectados mas sem recuo (pullback) intermediário suficiente (abaixo de epsilon)"
                estado["pattern_status"] = "FALSE_PEAK_BELOW_EPSILON"
                estado["last_rejection_reason"] = motivo
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": False,
                    "pattern_status": "FALSE_PEAK_BELOW_EPSILON",
                    "confirmation_tick": None,
                    "picos_detectados": len(picos_idx),
                    "preco_pico_1": serie[picos_idx[-2]],
                    "preco_pico_2": serie[picos_idx[-1]],
                    "razao": motivo,
                    "telemetria": {"epsilon": epsilon},
                }

            i1, i2 = par_valido
            p1_preco = serie[i1]
            p2_preco = serie[i2]
            k = (n - 1) - i2  # ticks decorridos após o 2º pico

            if k == 0:
                motivo = "Segundo pico acabou de ocorrer, aguardando início da janela de confirmação (tick 0)"
                estado["pattern_status"] = "SECOND_PEAK_FORMING"
                estado["last_rejection_reason"] = motivo
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": False,
                    "pattern_status": "SECOND_PEAK_FORMING",
                    "confirmation_tick": 0,
                    "picos_detectados": 2,
                    "preco_pico_1": p1_preco,
                    "preco_pico_2": p2_preco,
                    "razao": motivo,
                    "telemetria": {"k": 0, "epsilon": epsilon},
                }

            if k > max_window:
                motivo = f"Janela de confirmação expirada ({k} ticks após segundo pico > {max_window})"
                estado["pattern_status"] = "TIMING_2_4_EXPIRED"
                estado["last_rejection_reason"] = motivo
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": False,
                    "pattern_status": "TIMING_2_4_EXPIRED",
                    "confirmation_tick": k,
                    "picos_detectados": 2,
                    "preco_pico_1": p1_preco,
                    "preco_pico_2": p2_preco,
                    "razao": motivo,
                    "telemetria": {"k": k, "max_window": max_window},
                }

            # Dentro da janela de 1 a 4 ticks (k in 1..4):
            # 1. Verifica continuação de tendência (rompimento de máximas)
            if preco_atual > p2_preco + (epsilon * 0.1):
                motivo = f"Tendência de alta acelerando: preço rompeu segundo pico no tick {k} ({preco_atual:.2f} > {p2_preco:.2f})"
                estado["pattern_status"] = "CONTINUATION_BLOCKED"
                estado["last_rejection_reason"] = motivo
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": False,
                    "pattern_status": "CONTINUATION_BLOCKED",
                    "confirmation_tick": k,
                    "picos_detectados": 2,
                    "preco_pico_1": p1_preco,
                    "preco_pico_2": p2_preco,
                    "razao": motivo,
                    "telemetria": {"k": k, "preco_atual": preco_atual, "p2_preco": p2_preco},
                }

            # 2. Confirmação de rejeição objetiva e slope virando (exige recuo mínimo >= epsilon * 0.4)
            rejeitou = (p2_preco - preco_atual) >= (epsilon * 0.4)
            slope_curto = (serie[-1] - serie[-min(k + 1, 3)]) / float(min(k, 2)) if k >= 1 else 0.0
            slope_virou = slope_curto <= 0.0001

            if rejeitou and slope_virou:
                motivo = f"Timing 2/4 PUT confirmado no tick {k}/4 (P1: {p1_preco:.2f}, P2: {p2_preco:.2f}, Preço: {preco_atual:.2f})"
                estado["pattern_status"] = "CONFIRMED"
                estado["confirmation_tick"] = k
                estado["last_rejection_reason"] = ""
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": True,
                    "pattern_status": "CONFIRMED",
                    "confirmation_tick": k,
                    "picos_detectados": 2,
                    "preco_pico_1": p1_preco,
                    "preco_pico_2": p2_preco,
                    "razao": motivo,
                    "telemetria": {
                        "k": k,
                        "p1": p1_preco,
                        "p2": p2_preco,
                        "preco_atual": preco_atual,
                        "slope_curto": slope_curto,
                    },
                }
            else:
                motivo = f"Janela aberta (tick {k}/4): aguardando rejeição objetiva e slope descendente"
                estado["pattern_status"] = "AWAITING_CONFIRMATION"
                estado["last_rejection_reason"] = motivo
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": False,
                    "pattern_status": "AWAITING_CONFIRMATION",
                    "confirmation_tick": k,
                    "picos_detectados": 2,
                    "preco_pico_1": p1_preco,
                    "preco_pico_2": p2_preco,
                    "razao": motivo,
                    "telemetria": {"k": k, "rejeitou": rejeitou, "slope_virou": slope_virou},
                }

        elif direcao_pretendida == "CALL":
            # Busca dois fundos inferiores (mínimos locais)
            # Um fundo ocorre em i se serie[i] < serie[i-1] e serie[i] <= serie[i+1]
            fundos_idx = []
            for i in range(1, n - 1):
                if serie[i] < serie[i - 1] and serie[i] <= serie[i + 1]:
                    if (max(serie[i - 1], serie[i + 1]) - serie[i]) >= epsilon * 0.4:
                        fundos_idx.append(i)

            if n >= 2 and serie[-1] < serie[-2] and (serie[-2] - serie[-1]) >= epsilon * 0.4:
                fundos_idx.append(n - 1)

            if len(fundos_idx) < 2:
                # Dois ticks consecutivos de queda NÃO contam como dois fundos
                motivo = "Menos de 2 fundos inferiores confirmados"
                estado["pattern_status"] = "NO_TWO_TROUGHS"
                estado["last_rejection_reason"] = motivo
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": False,
                    "pattern_status": "NO_TWO_TROUGHS",
                    "confirmation_tick": None,
                    "picos_detectados": len(fundos_idx),
                    "preco_pico_1": serie[fundos_idx[0]] if fundos_idx else None,
                    "preco_pico_2": None,
                    "razao": motivo,
                    "telemetria": {"epsilon": epsilon, "fundos_idx": fundos_idx},
                }

            # Encontra o par mais recente de fundos com repique intermediário >= epsilon
            par_valido = None
            for f2_cand in reversed(fundos_idx):
                for f1_cand in reversed([f for f in fundos_idx if f < f2_cand]):
                    picos_entre = [serie[j] for j in range(f1_cand + 1, f2_cand)]
                    if picos_entre:
                        max_repique = max(picos_entre)
                        repique_f1 = max_repique - serie[f1_cand]
                        repique_f2 = max_repique - serie[f2_cand]
                        if repique_f1 >= epsilon and repique_f2 >= epsilon:
                            par_valido = (f1_cand, f2_cand)
                            break
                if par_valido:
                    break

            if not par_valido:
                motivo = "Dois fundos detectados mas sem repique intermediário suficiente (abaixo de epsilon)"
                estado["pattern_status"] = "FALSE_PEAK_BELOW_EPSILON"
                estado["last_rejection_reason"] = motivo
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": False,
                    "pattern_status": "FALSE_PEAK_BELOW_EPSILON",
                    "confirmation_tick": None,
                    "picos_detectados": len(fundos_idx),
                    "preco_pico_1": serie[fundos_idx[-2]],
                    "preco_pico_2": serie[fundos_idx[-1]],
                    "razao": motivo,
                    "telemetria": {"epsilon": epsilon},
                }

            i1, i2 = par_valido
            f1_preco = serie[i1]
            f2_preco = serie[i2]
            k = (n - 1) - i2  # ticks decorridos após o 2º fundo

            if k == 0:
                motivo = "Segundo fundo acabou de ocorrer, aguardando início da janela de confirmação (tick 0)"
                estado["pattern_status"] = "SECOND_TROUGH_FORMING"
                estado["last_rejection_reason"] = motivo
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": False,
                    "pattern_status": "SECOND_TROUGH_FORMING",
                    "confirmation_tick": 0,
                    "picos_detectados": 2,
                    "preco_pico_1": f1_preco,
                    "preco_pico_2": f2_preco,
                    "razao": motivo,
                    "telemetria": {"k": 0, "epsilon": epsilon},
                }

            if k > max_window:
                motivo = f"Janela de confirmação expirada ({k} ticks após segundo fundo > {max_window})"
                estado["pattern_status"] = "TIMING_2_4_EXPIRED"
                estado["last_rejection_reason"] = motivo
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": False,
                    "pattern_status": "TIMING_2_4_EXPIRED",
                    "confirmation_tick": k,
                    "picos_detectados": 2,
                    "preco_pico_1": f1_preco,
                    "preco_pico_2": f2_preco,
                    "razao": motivo,
                    "telemetria": {"k": k, "max_window": max_window},
                }

            # Dentro da janela de 1 a 4 ticks:
            # 1. Verifica continuação de queda (faca caindo / rompimento de mínimas)
            if preco_atual < f2_preco - (epsilon * 0.1):
                motivo = f"Tendência de baixa acelerando: preço rompeu segundo fundo no tick {k} ({preco_atual:.2f} < {f2_preco:.2f})"
                estado["pattern_status"] = "CONTINUATION_BLOCKED"
                estado["last_rejection_reason"] = motivo
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": False,
                    "pattern_status": "CONTINUATION_BLOCKED",
                    "confirmation_tick": k,
                    "picos_detectados": 2,
                    "preco_pico_1": f1_preco,
                    "preco_pico_2": f2_preco,
                    "razao": motivo,
                    "telemetria": {"k": k, "preco_atual": preco_atual, "f2_preco": f2_preco},
                }

            # 2. Confirmação de rejeição e slope ascendente (exige repique mínimo >= epsilon * 0.4)
            rejeitou = (preco_atual - f2_preco) >= (epsilon * 0.4)
            slope_curto = (serie[-1] - serie[-min(k + 1, 3)]) / float(min(k, 2)) if k >= 1 else 0.0
            slope_virou = slope_curto >= -0.0001

            if rejeitou and slope_virou:
                motivo = f"Timing 2/4 CALL confirmado no tick {k}/4 (F1: {f1_preco:.2f}, F2: {f2_preco:.2f}, Preço: {preco_atual:.2f})"
                estado["pattern_status"] = "CONFIRMED"
                estado["confirmation_tick"] = k
                estado["last_rejection_reason"] = ""
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": True,
                    "pattern_status": "CONFIRMED",
                    "confirmation_tick": k,
                    "picos_detectados": 2,
                    "preco_pico_1": f1_preco,
                    "preco_pico_2": f2_preco,
                    "razao": motivo,
                    "telemetria": {
                        "k": k,
                        "f1": f1_preco,
                        "f2": f2_preco,
                        "preco_atual": preco_atual,
                        "slope_curto": slope_curto,
                    },
                }
            else:
                motivo = f"Janela aberta (tick {k}/4): aguardando rejeição objetiva e slope ascendente"
                estado["pattern_status"] = "AWAITING_CONFIRMATION"
                estado["last_rejection_reason"] = motivo
                return {
                    "ativo": simbolo,
                    "direcao": direcao_pretendida,
                    "aprovado": False,
                    "pattern_status": "AWAITING_CONFIRMATION",
                    "confirmation_tick": k,
                    "picos_detectados": 2,
                    "preco_pico_1": f1_preco,
                    "preco_pico_2": f2_preco,
                    "razao": motivo,
                    "telemetria": {"k": k, "rejeitou": rejeitou, "slope_virou": slope_virou},
                }

        return {
            "ativo": simbolo,
            "direcao": direcao_pretendida,
            "aprovado": False,
            "pattern_status": "UNKNOWN_DIRECTION",
            "confirmation_tick": None,
            "picos_detectados": 0,
            "preco_pico_1": None,
            "preco_pico_2": None,
            "razao": f"Direção pretendida desconhecida: {direcao_pretendida}",
            "telemetria": {},
        }


# Instâncias canônicas globais dos componentes
detector_timing_24 = Timing24Detector()
classificador_regime = RegimeClassifier()


def obter_timing_24_detector() -> Timing24Detector:
    return detector_timing_24


def obter_regime_classifier() -> RegimeClassifier:
    return classificador_regime


class ExtremeDetector:
    """
    Detector de Extremos Estatísticos.
    Identifica quando o ativo atingiu níveis extremos de sobrecompra ou sobrevenda
    utilizando percentis históricos, z-score, bandas de Bollinger e RSI.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg_micro = getattr(global_config, "MICRO_SCALPER_CONFIG", {})
        self.config = config or cfg_micro.get("extremo", {
            "percentile_low": 5.0,
            "percentile_high": 95.0,
            "z_score_threshold": 2.0,
            "rsi_oversold": 25.0,
            "rsi_overbought": 75.0,
            "bb_period": 20,
            "bb_std": 2.0,
        })

    def detectar(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Avalia se o snapshot de mercado representa um extremo estatístico.
        Retorna diagnóstico completo com justificativa.
        """
        preco_atual = snapshot.get("preco_atual", 0.0)
        ticks_count = snapshot.get("ticks_count", 0)

        if preco_atual <= 0 or ticks_count < 10:
            return {
                "extremo_detectado": False,
                "tipo_extremo": None,
                "direcao_pretendida": None,
                "pontuacao_extremo": 0.0,
                "razao": f"Dados insuficientes para detecção de extremo (ticks: {ticks_count})",
                "detalhes": {},
            }

        percentil_curto = snapshot.get("percentil_curto", 50.0)
        percentil_medio = snapshot.get("percentil_medio", 50.0)
        z_score = snapshot.get("z_score", 0.0)
        z_score_medio = snapshot.get("z_score_medio", z_score)
        rsi = snapshot.get("rsi", 50.0)
        bb_superior = snapshot.get("bb_superior", preco_atual)
        bb_inferior = snapshot.get("bb_inferior", preco_atual)
        dist_bb_inf = snapshot.get("distancia_bb_inferior", 0.0)
        dist_bb_sup = snapshot.get("distancia_bb_superior", 0.0)

        p_low = self.config.get("percentile_low", 5.0)
        p_high = self.config.get("percentile_high", 95.0)
        z_thresh = self.config.get("z_score_threshold", 2.0)
        rsi_os = self.config.get("rsi_oversold", 25.0)
        rsi_ob = self.config.get("rsi_overbought", 75.0)

        # Condição 1: Extremo Baixo (Sobrevenda -> Oportunidade CALL)
        cond_percentil_baixo = (percentil_curto <= p_low) or (percentil_medio <= p_low * 2.5 and percentil_curto <= 30.0)
        cond_z_baixo = (z_score <= -z_thresh) or (z_score_medio <= -z_thresh and percentil_curto <= 30.0)
        cond_rsi_baixo = rsi <= (rsi_os + 5.0)
        cond_bb_baixo = (dist_bb_inf <= 0.02) or (preco_atual <= bb_inferior)

        # Condição 2: Extremo Alto (Sobrecompra -> Oportunidade PUT)
        cond_percentil_alto = (percentil_curto >= p_high) or (percentil_medio >= 100.0 - (p_low * 2.5) and percentil_curto >= 70.0)
        cond_z_alto = (z_score >= z_thresh) or (z_score_medio >= z_thresh and percentil_curto >= 70.0)
        cond_rsi_alto = rsi >= (rsi_ob - 5.0)
        cond_bb_alto = (dist_bb_sup <= 0.02) or (preco_atual >= bb_superior)

        detalhes = {
            "percentil_curto": percentil_curto,
            "percentil_medio": percentil_medio,
            "z_score": z_score,
            "z_score_medio": z_score_medio,
            "rsi": rsi,
            "dist_bb_inf": dist_bb_inf,
            "dist_bb_sup": dist_bb_sup,
        }

        # Avaliação de Extremo Baixo (CALL)
        confluencias_baixas = sum([cond_percentil_baixo, cond_z_baixo, cond_rsi_baixo, cond_bb_baixo])
        if confluencias_baixas >= 2 and (cond_percentil_baixo or cond_z_baixo):
            pontos = 15.0
            if cond_percentil_baixo:
                pontos += 5.0
            if cond_z_baixo:
                pontos += 5.0
            pontos = min(25.0, pontos)
            return {
                "extremo_detectado": True,
                "tipo_extremo": "BAIXO",
                "direcao_pretendida": "CALL",
                "pontuacao_extremo": round(pontos, 1),
                "razao": f"Extremo Baixo: Pctl({percentil_curto:.1f}%), Z({z_score:.2f}), RSI({rsi:.1f})",
                "detalhes": detalhes,
            }

        # Avaliação de Extremo Alto (PUT)
        confluencias_altas = sum([cond_percentil_alto, cond_z_alto, cond_rsi_alto, cond_bb_alto])
        if confluencias_altas >= 2 and (cond_percentil_alto or cond_z_alto):
            pontos = 15.0
            if cond_percentil_alto:
                pontos += 5.0
            if cond_z_alto:
                pontos += 5.0
            pontos = min(25.0, pontos)
            return {
                "extremo_detectado": True,
                "tipo_extremo": "ALTO",
                "direcao_pretendida": "PUT",
                "pontuacao_extremo": round(pontos, 1),
                "razao": f"Extremo Alto: Pctl({percentil_curto:.1f}%), Z({z_score:.2f}), RSI({rsi:.1f})",
                "detalhes": detalhes,
            }

        # Sem extremo claro
        return {
            "extremo_detectado": False,
            "tipo_extremo": None,
            "direcao_pretendida": None,
            "pontuacao_extremo": 0.0,
            "razao": f"Mercado em faixa normal (Pctl: {percentil_curto:.1f}%, Z: {z_score:.2f}, RSI: {rsi:.1f})",
            "detalhes": detalhes,
        }


class ReversalConfirmator:
    """
    Confirmador de Reversão.
    REGRA MANDATÓRIA: NÃO COMPRAR UMA QUEDA SÓ PORQUE ESTÁ BAIXA.
    Exige esgotamento da força direcional prévia e comprovação de virada (reversão)
    através de sequência de ticks na direção oposta, desaceleração do slope e inflexão do RSI.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg_micro = getattr(global_config, "MICRO_SCALPER_CONFIG", {})
        self.config = config or cfg_micro.get("reversao", {
            "min_reversal_ticks": 3,
            "rsi_exit_margin": 2.0,
            "min_ticks_desaceleracao": 2,
        })

    def confirmar(
        self,
        direcao_pretendida: str,
        ultimos_ticks: List[float],
        snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Valida se há confirmação empírica de reversão para a direção pretendida.
        """
        min_ticks = self.config.get("min_reversal_ticks", 3)

        if len(ultimos_ticks) < min_ticks + 2:
            return {
                "reversao_confirmada": False,
                "pontuacao_reversao": 0.0,
                "ticks_confirmados": 0,
                "rsi_virou": False,
                "razao": f"Histórico de ticks insuficiente ({len(ultimos_ticks)}/{min_ticks + 2})",
                "detalhes": {},
            }

        ticks_recentes = ultimos_ticks[-(min_ticks + 3):]
        rsi_atual = snapshot.get("rsi", 50.0)
        inclinacao_curta = snapshot.get("inclinacao_curta", 0.0)

        # 1. Contagem de ticks consecutivos na direção oposta
        deltas = [ticks_recentes[i] - ticks_recentes[i - 1] for i in range(1, len(ticks_recentes))]
        
        ticks_consecutivos = 0
        if direcao_pretendida == "CALL":
            for d in reversed(deltas):
                if d >= 0:
                    ticks_consecutivos += 1
                else:
                    break
        elif direcao_pretendida == "PUT":
            for d in reversed(deltas):
                if d <= 0:
                    ticks_consecutivos += 1
                else:
                    break

        preco_atual = ticks_recentes[-1]
        precos_anteriores = ticks_recentes[:-1]

        # 2. Desaceleração / Inflexão do Slope e deltas favoráveis recentes
        ultimos_deltas = deltas[-3:] if len(deltas) >= 3 else deltas
        desacelerando = False
        rejeicao_extremo = False
        virada = False

        if direcao_pretendida == "CALL":
            ticks_favoraveis_recentes = sum(1 for d in ultimos_deltas if d >= 0)
            ultimo_delta_favoravel = deltas[-1] >= 0 if deltas else False
            deslocamento_recente = (ticks_recentes[-1] - ticks_recentes[-3]) if len(ticks_recentes) >= 3 else (deltas[-1] if deltas else 0.0)
            
            min_extremo = min(ticks_recentes)
            rejeicao_extremo = (preco_atual > min_extremo) or (preco_atual >= min(precos_anteriores))
            desacelerando = (inclinacao_curta >= -0.05) or (len(deltas) >= 2 and deltas[-1] > deltas[-2]) or ultimo_delta_favoravel
            
            virada = (
                (ticks_consecutivos >= 2)
                or (ticks_consecutivos >= 1 and (ticks_favoraveis_recentes >= 2 or deslocamento_recente > 0))
                or (desacelerando and ultimo_delta_favoravel and rejeicao_extremo)
            )
            ticks_aprovados = max(ticks_consecutivos, ticks_favoraveis_recentes)

        elif direcao_pretendida == "PUT":
            ticks_favoraveis_recentes = sum(1 for d in ultimos_deltas if d <= 0)
            ultimo_delta_favoravel = deltas[-1] <= 0 if deltas else False
            deslocamento_recente = (ticks_recentes[-3] - ticks_recentes[-1]) if len(ticks_recentes) >= 3 else (-deltas[-1] if deltas else 0.0)
            
            max_extremo = max(ticks_recentes)
            rejeicao_extremo = (preco_atual < max_extremo) or (preco_atual <= max(precos_anteriores))
            desacelerando = (inclinacao_curta <= 0.05) or (len(deltas) >= 2 and deltas[-1] < deltas[-2]) or ultimo_delta_favoravel
            
            virada = (
                (ticks_consecutivos >= 2)
                or (ticks_consecutivos >= 1 and (ticks_favoraveis_recentes >= 2 or deslocamento_recente > 0))
                or (desacelerando and ultimo_delta_favoravel and rejeicao_extremo)
            )
            ticks_aprovados = max(ticks_consecutivos, ticks_favoraveis_recentes)
        else:
            ticks_aprovados = 0

        # Critério de aprovação rigoroso: virada demonstrada E rejeição real do extremo
        # NUNCA compra CALL se estiver renovando mínimas e NUNCA compra PUT se estiver renovando máximas
        confirmado = virada and rejeicao_extremo

        pontuacao = 0.0
        if confirmado:
            pontuacao = 10.0
            if ticks_consecutivos >= 2 or ticks_aprovados >= 2:
                pontuacao += 5.0
            if desacelerando:
                pontuacao += 5.0
            pontuacao = min(20.0, pontuacao)

        razao = (
            f"Reversão confirmada ({ticks_aprovados} ticks favoráveis, slope: {inclinacao_curta:.3f})"
            if confirmado
            else f"Aguardando reversão: ticks favoráveis={ticks_aprovados}/{min_ticks}, rejeição={rejeicao_extremo}"
        )

        return {
            "reversao_confirmada": confirmado,
            "pontuacao_reversao": round(pontuacao, 1),
            "ticks_confirmados": ticks_aprovados,
            "rejeicao_extremo": rejeicao_extremo,
            "desacelerando": desacelerando,
            "razao": razao,
            "detalhes": {
                "ticks_favoraveis": ticks_consecutivos,
                "ticks_aprovados": ticks_aprovados,
                "inclinacao_curta": inclinacao_curta,
                "rejeicao_extremo": rejeicao_extremo,
            },
        }


class ConfluenceScore:
    """
    Score de Confluência Ponderado.
    Calcula pontuação de 0 a 100 com base em múltiplos fatores independentes:
    - Extremo estatístico (percentil + z-score): até 25 pts
    - Bollinger Bands (toque/rompimento): até 15 pts
    - RSI extremo e inflexão: até 15 pts
    - Distância das Médias Móveis (esticamento): até 15 pts
    - Confirmação de reversão (ticks + slope): até 20 pts
    - Saúde do mercado (volatilidade e dados): até 10 pts

    Sinal SOMENTE emitido se Score >= min_score (padrão: 85).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg_micro = getattr(global_config, "MICRO_SCALPER_CONFIG", {})
        self.config = config or cfg_micro.get("score", {
            "min_score": 85.0,
            "pesos": {
                "extremo_estatistico": 25.0,
                "bollinger": 15.0,
                "rsi_extremo": 15.0,
                "distancia_ema": 15.0,
                "confirmacao_reversao": 20.0,
                "saude_mercado": 10.0,
            },
        })
        self.min_score = self.config.get("min_score", 85.0)

    def obter_min_score_perfil(self, modo: Optional[str] = None) -> float:
        """Retorna o score mínimo calibrado por perfil ou o padrão da config."""
        env_score = os.getenv("SCALPER_MIN_SCORE")
        if env_score:
            try:
                return float(env_score)
            except ValueError:
                pass

        m = (modo or "").lower().strip()
        if m == "agressivo":
            return 65.0
        elif m in ["conservador", "intermediario"]:
            return 70.0
        elif m == "iniciante":
            return 72.0
        return self.min_score

    def calcular(
        self,
        direcao_pretendida: str,
        extremo_res: Dict[str, Any],
        reversao_res: Dict[str, Any],
        snapshot: Dict[str, Any],
        modo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calcula o score de confluência final e decide se emite sinal.
        """
        scores = {}

        # 1. Extremo estatístico (0 a 25)
        scores["extremo_estatistico"] = extremo_res.get("pontuacao_extremo", 0.0)

        # 2. Bollinger Bands (0 a 15)
        preco_atual = snapshot.get("preco_atual", 0.0)
        bb_superior = snapshot.get("bb_superior", preco_atual)
        bb_inferior = snapshot.get("bb_inferior", preco_atual)
        bb_media = snapshot.get("bb_media", preco_atual)

        bb_score = 0.0
        if direcao_pretendida == "CALL":
            if preco_atual <= bb_inferior:
                bb_score = 15.0
            elif bb_media > bb_inferior and preco_atual < (bb_inferior + (bb_media - bb_inferior) * 0.4):
                bb_score = 12.0
            elif bb_media > bb_inferior and preco_atual < (bb_inferior + (bb_media - bb_inferior) * 0.6):
                bb_score = 8.0
        elif direcao_pretendida == "PUT":
            if preco_atual >= bb_superior:
                bb_score = 15.0
            elif bb_superior > bb_media and preco_atual > (bb_superior - (bb_superior - bb_media) * 0.4):
                bb_score = 12.0
            elif bb_superior > bb_media and preco_atual > (bb_superior - (bb_superior - bb_media) * 0.6):
                bb_score = 8.0
        scores["bollinger"] = bb_score

        # 3. RSI extremo (0 a 15)
        rsi = snapshot.get("rsi", 50.0)
        rsi_score = 0.0
        if direcao_pretendida == "CALL":
            if rsi <= 25.0:
                rsi_score = 15.0
            elif rsi <= 30.0:
                rsi_score = 12.0
            elif rsi <= 35.0:
                rsi_score = 8.0
        elif direcao_pretendida == "PUT":
            if rsi >= 75.0:
                rsi_score = 15.0
            elif rsi >= 70.0:
                rsi_score = 12.0
            elif rsi >= 65.0:
                rsi_score = 8.0
        scores["rsi_extremo"] = rsi_score

        # 4. Distância das EMAs (0 a 15)
        ema_rapida = snapshot.get("ema_rapida", preco_atual)
        ema_score = 0.0
        if preco_atual > 0:
            dist_ema_rapida = abs(preco_atual - ema_rapida) / preco_atual
            if direcao_pretendida == "CALL" and preco_atual < ema_rapida:
                if dist_ema_rapida >= 0.0008:
                    ema_score = 15.0
                else:
                    ema_score = 10.0
            elif direcao_pretendida == "PUT" and preco_atual > ema_rapida:
                if dist_ema_rapida >= 0.0008:
                    ema_score = 15.0
                else:
                    ema_score = 10.0
            else:
                ema_score = 5.0
        scores["distancia_ema"] = ema_score

        # 5. Confirmação de reversão (0 a 20)
        scores["confirmacao_reversao"] = reversao_res.get("pontuacao_reversao", 0.0)

        # 6. Saúde do mercado (0 a 10)
        volatilidade = snapshot.get("volatilidade_instantanea", 0.0)
        ticks_count = snapshot.get("ticks_count", 0)
        saude_score = 0.0
        if ticks_count >= 30 and volatilidade > 0:
            saude_score = 10.0
        elif ticks_count >= 15:
            saude_score = 6.0
        scores["saude_mercado"] = saude_score

        # Soma ponderada
        score_total = sum(scores.values())
        score_total = min(100.0, round(score_total, 1))

        target_min_score = self.obter_min_score_perfil(modo)
        aprovado = (score_total >= target_min_score) and reversao_res.get("reversao_confirmada", False)

        motivos_recusa = []
        if not extremo_res.get("extremo_detectado", False):
            motivos_recusa.append("Sem extremo estatístico confirmado")
        if not reversao_res.get("reversao_confirmada", False):
            motivos_recusa.append(f"Reversão não confirmada ({reversao_res.get('razao')})")
        if score_total < target_min_score:
            motivos_recusa.append(f"Score {score_total:.1f} abaixo do mínimo {target_min_score:.1f}")

        motivo_recusa_str = " | ".join(motivos_recusa) if motivos_recusa else ""

        return {
            "aprovado": aprovado,
            "score": score_total,
            "min_score": target_min_score,
            "scores_detalhados": scores,
            "sinal": direcao_pretendida if aprovado else None,
            "motivo_recusa": motivo_recusa_str,
            "razao": (
                f"SINAL {direcao_pretendida} CONFIRMADO (Score {score_total:.1f}/{target_min_score:.1f})"
                if aprovado
                else f"Recusado: {motivo_recusa_str}"
            ),
        }


class MicroScalperStateMachine:
    """
    Máquina de Estados Finita do Micro-Scalper.
    Estados:
    - NORMAL: Monitorando mercado e calculando estatísticas
    - EXTREMO_DETECTADO: Extremo estatístico identificado
    - AGUARDANDO_REVERSAO: Aguardando virada de ticks e inflexão
    - SINAL_CONFIRMADO: Extremo + Reversão + Confluence Score >= 85
    - VALIDANDO_RISCO: Gateway de risco checando spread, stale data, max open positions
    - COMPRANDO: Ordem em trânsito na Deriv API
    - POSICAO_ABERTA: Contrato em monitoramento via WebSocket
    - SAINDO: Disparo de venda no primeiro lucro líquido positivo
    - COOLDOWN: Intervalo pós-operação para evitar overtrading
    """

    def __init__(self):
        self.estado_atual = MicroScalperState.NORMAL
        self.tempo_mudanca_estado = time.time()
        self.ultimo_sinal = None
        self.ultimo_score = 0.0
        self.ultimo_motivo_recusa = "Aguardando inicialização"
        self.historico_estados: List[Dict[str, Any]] = []
        self.total_sinais_gerados = 0
        self.total_operacoes_concluidas = 0
        self.operacoes_vitoriosas = 0
        self.operacoes_derrotadas = 0
        self.dados_ultimo_extremo: Optional[Dict[str, Any]] = None
        self.timestamp_ultimo_extremo: float = 0.0
        self.direcao_reversao: Optional[str] = None

    def transitar(self, novo_estado: str, motivo: str = ""):
        """Registra a transição de estado garantindo rastreabilidade."""
        if self.estado_atual != novo_estado:
            agora = time.time()
            duracao_anterior = agora - self.tempo_mudanca_estado
            logger_intel.info(
                f"🔄 Transição de Estado: [{self.estado_atual}] -> [{novo_estado}] "
                f"(Duração anterior: {duracao_anterior:.2f}s) - Motivo: {motivo}"
            )
            self.historico_estados.append({
                "de": self.estado_atual,
                "para": novo_estado,
                "tempo": datetime.now().isoformat(),
                "duracao_segundos": round(duracao_anterior, 2),
                "motivo": motivo,
            })
            if len(self.historico_estados) > 100:
                self.historico_estados.pop(0)

            self.estado_atual = novo_estado
            self.tempo_mudanca_estado = agora

    def registrar_resultado_operacao(self, lucro: float, motivo_saida: str):
        """Atualiza estatísticas de desempenho empírico."""
        self.total_operacoes_concluidas += 1
        if lucro > 0:
            self.operacoes_vitoriosas += 1
        else:
            self.operacoes_derrotadas += 1

    def obter_win_rate(self) -> float:
        """Calcula o win rate real observado."""
        if self.total_operacoes_concluidas == 0:
            return 0.0
        return round((self.operacoes_vitoriosas / self.total_operacoes_concluidas) * 100, 2)

    def obter_telemetria(self) -> Dict[str, Any]:
        """Retorna snapshot completo da telemetria da máquina de estados."""
        tempo_no_estado = round(time.time() - self.tempo_mudanca_estado, 1)
        return {
            "estado_atual": self.estado_atual,
            "tempo_no_estado_s": tempo_no_estado,
            "ultimo_score": self.ultimo_score,
            "ultimo_motivo_recusa": self.ultimo_motivo_recusa,
            "total_sinais": self.total_sinais_gerados,
            "total_operacoes": self.total_operacoes_concluidas,
            "operacoes_vitoriosas": self.operacoes_vitoriosas,
            "operacoes_derrotadas": self.operacoes_derrotadas,
            "win_rate_observado": self.obter_win_rate(),
        }


# Instância global da máquina de estados do módulo (fallback compatível)
state_machine_micro_scalper = MicroScalperStateMachine()

# Registro de state machines isoladas por ativo (Issue #20)
state_machines_por_ativo: Dict[str, MicroScalperStateMachine] = {}


def obter_state_machine(ativo: Optional[str] = None) -> MicroScalperStateMachine:
    """Retorna a state machine isolada para o ativo especificado ou a padrão global."""
    if not ativo:
        return state_machine_micro_scalper
    simbolo = str(ativo).upper().strip()
    if simbolo not in state_machines_por_ativo:
        state_machines_por_ativo[simbolo] = MicroScalperStateMachine()
    return state_machines_por_ativo[simbolo]


def analisar_micro_scalping(
    dados_ou_snapshot: Any,
    meta: float = 20.0,
    lucro_atual: float = 0.0,
    modo: str = "iniciante",
    operacoes_ativas: int = 0,
    ultimos_ticks: Optional[List[float]] = None,
    ativo: Optional[str] = None,
    state_machine: Optional[MicroScalperStateMachine] = None,
    usar_timing_2_4: bool = False,
    usar_filtro_regime: bool = False,
) -> Dict[str, Any]:
    """
    ANÁLISE CANÔNICA DO MICRO-SCALPER SELETIVO (Issues #2, #3, #4, #13, #17, #20).
    Substitui qualquer lógica aleatória por análise estatística determinística.
    Integra ExtremeDetector, ReversalConfirmator, ConfluenceScore, StateMachine,
    Timing24Detector (#13) e RegimeClassifier (#17).
    Suporta concorrência 3 / 5 / 10 posições simultâneas e state machine isolada por ativo.
    """
    try:
        # Se ativo não foi passado explicitamente, tenta extrair do snapshot se for dict
        if not ativo and isinstance(dados_ou_snapshot, dict):
            ativo = dados_ou_snapshot.get("ativo") or dados_ou_snapshot.get("simbolo")

        ativo_str = str(ativo or "GLOBAL").upper().strip()
        sm = state_machine or obter_state_machine(ativo_str)

        # Destrava automática caso tenha ficado em COMPRANDO por mais de 8s (falha de rede / timeout)
        agora_check = time.time()
        if sm.estado_atual == MicroScalperState.COMPRANDO and (agora_check - sm.tempo_mudanca_estado) > 8.0:
            sm.transitar(MicroScalperState.NORMAL, "Recuperação automática de timeout em COMPRANDO")
        if state_machine_micro_scalper.estado_atual == MicroScalperState.COMPRANDO and (agora_check - state_machine_micro_scalper.tempo_mudanca_estado) > 8.0:
            state_machine_micro_scalper.transitar(MicroScalperState.NORMAL, "Recuperação automática de timeout em COMPRANDO")

        # 1. Checagem de meta diária atingida
        if meta > 0 and lucro_atual >= meta:
            sm.transitar(MicroScalperState.NORMAL, "Meta diária atingida")
            sm.ultimo_motivo_recusa = f"Meta diária de ${meta:.2f} atingida"
            return {
                "sinal": None,
                "confianca": 0.0,
                "score": 0.0,
                "estado": sm.estado_atual,
                "razao": f"Meta diária de ${meta:.2f} já atingida (Lucro atual: ${lucro_atual:.2f})",
                "motivo_recusa": sm.ultimo_motivo_recusa,
            }

        # 2. Checagem de operações ativas (Limite dinâmico por perfil: 3 / 5 / 10)
        limite_pos = obter_limite_posicoes(modo)
        if operacoes_ativas >= limite_pos:
            sm.transitar(MicroScalperState.POSICAO_ABERTA, f"Limite de posições atingido ({operacoes_ativas}/{limite_pos})")
            sm.ultimo_motivo_recusa = f"Limite de operações simultâneas atingido ({operacoes_ativas}/{limite_pos})"
            return {
                "sinal": None,
                "confianca": 0.0,
                "score": sm.ultimo_score,
                "estado": sm.estado_atual,
                "razao": f"Aguardando liberação de vagas no perfil '{modo}' ({operacoes_ativas}/{limite_pos})",
                "motivo_recusa": sm.ultimo_motivo_recusa,
            }

        # 3. Normalização dos dados de entrada (pode receber snapshot dict ou lista de velas)
        snapshot: Dict[str, Any] = {}
        ticks: List[float] = ultimos_ticks or []

        if isinstance(dados_ou_snapshot, dict) and "preco_atual" in dados_ou_snapshot:
            snapshot = dados_ou_snapshot
            if not ticks and "ultimos_ticks" in snapshot:
                ticks = snapshot["ultimos_ticks"]
        elif isinstance(dados_ou_snapshot, list) and len(dados_ou_snapshot) > 0:
            if isinstance(dados_ou_snapshot[0], dict):
                closes = [v["close"] for v in dados_ou_snapshot]
            else:
                closes = [float(x) for x in dados_ou_snapshot]
            
            preco_atual = closes[-1]
            ticks = closes[-60:]
            
            rsi = calcular_rsi_local(closes, 14)
            p_curto = float(np.percentile(closes[-20:], 50)) if len(closes) >= 20 else 50.0
            p_curto_val = (sum(1 for x in closes[-20:] if x <= preco_atual) / len(closes[-20:]) * 100) if len(closes) >= 20 else 50.0
            mean_c = np.mean(closes[-20:]) if len(closes) >= 20 else preco_atual
            std_c = np.std(closes[-20:]) if len(closes) >= 20 else 1.0
            z_score = (preco_atual - mean_c) / std_c if std_c > 0 else 0.0

            snapshot = {
                "preco_atual": preco_atual,
                "ticks_count": len(closes),
                "rsi": rsi,
                "percentil_curto": p_curto_val,
                "percentil_medio": p_curto_val,
                "z_score": z_score,
                "bb_superior": mean_c + 2.0 * std_c,
                "bb_inferior": mean_c - 2.0 * std_c,
                "bb_media": mean_c,
                "distancia_bb_superior": (mean_c + 2.0 * std_c - preco_atual) / preco_atual if preco_atual > 0 else 0.0,
                "distancia_bb_inferior": (preco_atual - (mean_c - 2.0 * std_c)) / preco_atual if preco_atual > 0 else 0.0,
                "ema_rapida": mean_c,
                "ema_lenta": mean_c,
                "inclinacao_curta": (closes[-1] - closes[-5]) / 5.0 if len(closes) >= 5 else 0.0,
                "volatilidade_instantanea": std_c / mean_c if mean_c > 0 else 0.0,
            }
        else:
            sm.ultimo_motivo_recusa = "Formato de dados não reconhecido"
            return {
                "sinal": None,
                "confianca": 0.0,
                "score": 0.0,
                "estado": sm.estado_atual,
                "razao": "Dados insuficientes ou inválidos",
                "motivo_recusa": sm.ultimo_motivo_recusa,
            }

        # 4. Detector de Extremos e Janela de Reversão
        detector = ExtremeDetector()
        extremo_res = detector.detectar(snapshot)
        confluence = ConfluenceScore()
        target_min_score = confluence.obter_min_score_perfil(modo)

        agora = time.time()
        janela_reversao_s = 10.0

        if extremo_res["extremo_detectado"]:
            direcao = extremo_res["direcao_pretendida"]
            sm.dados_ultimo_extremo = extremo_res
            sm.timestamp_ultimo_extremo = agora
            sm.direcao_reversao = direcao
            sm.transitar(
                MicroScalperState.EXTREMO_DETECTADO,
                f"Extremo {extremo_res['tipo_extremo']} detectado para {direcao}",
            )
            sm.transitar(MicroScalperState.AGUARDANDO_REVERSAO, f"Validando virada para {direcao}")
        elif (
            sm.estado_atual == MicroScalperState.AGUARDANDO_REVERSAO
            and getattr(sm, "dados_ultimo_extremo", None) is not None
            and (agora - getattr(sm, "timestamp_ultimo_extremo", 0.0)) <= janela_reversao_s
        ):
            # O preço está dentro da janela de reversão pós-extremo!
            extremo_res = sm.dados_ultimo_extremo
            direcao = sm.direcao_reversao or extremo_res.get("direcao_pretendida", "CALL")
        elif sm.estado_atual in (
            MicroScalperState.POSICAO_ABERTA,
            MicroScalperState.COMPRANDO,
            MicroScalperState.SAINDO,
            MicroScalperState.COOLDOWN,
        ):
            # Não reseta para NORMAL se o ativo já possui uma operação ativa ou em transição
            st_name = getattr(sm.estado_atual, "name", str(sm.estado_atual))
            return {
                "sinal": None,
                "confianca": 0.0,
                "score": getattr(sm, "ultimo_score", 0.0),
                "min_score": target_min_score,
                "estado": sm.estado_atual,
                "razao": f"Ativo em estado {st_name}",
                "motivo_recusa": f"Ativo em estado {st_name}",
                "analise": snapshot,
            }
        else:
            sm.dados_ultimo_extremo = None
            sm.direcao_reversao = None
            sm.transitar(MicroScalperState.NORMAL, "Mercado em faixa normal")
            sm.ultimo_motivo_recusa = extremo_res["razao"]
            sm.ultimo_score = 0.0
            return {
                "sinal": None,
                "confianca": 0.0,
                "score": 0.0,
                "min_score": target_min_score,
                "estado": sm.estado_atual,
                "razao": extremo_res["razao"],
                "motivo_recusa": extremo_res["razao"],
                "analise": snapshot,
            }

        # 5. FILTRO DE REGIME DE MERCADO (Issue #17)
        regime_res = None
        if usar_filtro_regime:
            regime_res = classificador_regime.classificar(
                ativo=ativo_str,
                ticks=ticks,
                snapshot=snapshot,
                direcao_pretendida=direcao,
            )
            if not regime_res["aprovado"]:
                sm.ultimo_motivo_recusa = f"Regime {regime_res['regime']}: {regime_res['razao']}"
                return {
                    "sinal": None,
                    "confianca": 0.0,
                    "score": 0.0,
                    "min_score": target_min_score,
                    "estado": sm.estado_atual,
                    "regime": regime_res["regime"],
                    "razao": regime_res["razao"],
                    "motivo_recusa": sm.ultimo_motivo_recusa,
                    "analise": snapshot,
                }

        # 6. FILTRO DE TIMING 2/4 POR TICKS (Issue #13)
        timing_res = None
        if usar_timing_2_4:
            timing_res = detector_timing_24.detectar(
                ativo=ativo_str,
                ticks=ticks,
                direcao_pretendida=direcao,
            )
            if not timing_res["aprovado"]:
                sm.ultimo_motivo_recusa = f"Timing 2/4 não confirmado: {timing_res['razao']}"
                return {
                    "sinal": None,
                    "confianca": 0.0,
                    "score": 0.0,
                    "min_score": target_min_score,
                    "estado": sm.estado_atual,
                    "timing_2_4": timing_res,
                    "razao": timing_res["razao"],
                    "motivo_recusa": sm.ultimo_motivo_recusa,
                    "analise": snapshot,
                }

        # 7. Confirmador de Reversão
        confirmador = ReversalConfirmator()
        reversao_res = confirmador.confirmar(direcao, ticks, snapshot)

        # 8. Score de Confluência calibrado por perfil
        score_res = confluence.calcular(direcao, extremo_res, reversao_res, snapshot, modo=modo)
        sm.ultimo_score = score_res["score"]

        if not score_res["aprovado"]:
            sm.ultimo_motivo_recusa = score_res["motivo_recusa"]
            return {
                "sinal": None,
                "confianca": round(score_res["score"] / 100.0, 2),
                "score": score_res["score"],
                "min_score": score_res["min_score"],
                "estado": sm.estado_atual,
                "razao": score_res["razao"],
                "motivo_recusa": score_res["motivo_recusa"],
                "scores_detalhados": score_res["scores_detalhados"],
                "analise": snapshot,
            }

        # Confluências auditáveis explícitas
        confluencias_audit = {
            "2_4_PATTERN": "PASS" if (timing_res and timing_res.get("aprovado")) else ("BYPASS" if not usar_timing_2_4 else "FAIL"),
            "EXTREMO": "PASS",
            "REJEICAO": "PASS" if reversao_res.get("rejeicao_extremo") else "FAIL",
            "SLOPE_REVERSAL": "PASS" if reversao_res.get("desacelerando") else "FAIL",
            "ACCELERATION_DECAY": "PASS" if reversao_res.get("desacelerando") else "FAIL",
            "REGIME": regime_res.get("regime", "REVERSAO_VALIDA") if regime_res else "REVERSAO_VALIDA",
            "VOLATILITY": "PASS",
            "TICKS_FRESH": "PASS",
        }

        # SINAL APROVADO COM EXTREMO + REVERSÃO + CONFLUÊNCIA (+ TIMING 2/4 / REGIME)!
        sm.transitar(
            MicroScalperState.SINAL_CONFIRMADO,
            f"Sinal {direcao} aprovado com score {score_res['score']:.1f}",
        )
        sm.total_sinais_gerados += 1
        sm.ultimo_sinal = direcao
        sm.ultimo_motivo_recusa = "Nenhum (Sinal ativo e confirmado)"
        sm.dados_ultimo_extremo = None
        sm.direcao_reversao = None

        return {
            "sinal": direcao,
            "tipo": direcao,
            "confianca": round(score_res["score"] / 100.0, 2),
            "score": score_res["score"],
            "min_score": score_res["min_score"],
            "estado": sm.estado_atual,
            "razao": score_res["razao"],
            "motivo_recusa": "",
            "scores_detalhados": score_res["scores_detalhados"],
            "confluencias": confluencias_audit,
            "timing_2_4": timing_res,
            "regime": regime_res.get("regime") if regime_res else "REVERSAO_VALIDA",
            "analise": snapshot,
        }

    except Exception as e:
        logger_intel.error(f"Erro na análise de micro scalping: {e}", exc_info=True)
        return {
            "sinal": None,
            "confianca": 0.0,
            "score": 0.0,
            "estado": MicroScalperState.NORMAL,
            "razao": f"Erro interno na inteligência: {str(e)}",
            "motivo_recusa": str(e),
        }


def executar_replay_ticks(
    historico_ticks: List[float],
    meta_lucro: float = 10.0,
    stake: float = 1.0,
    payout_ratio: float = 0.85,
    min_exit_profit: float = 0.05,
    max_hold_ticks: int = 15,
    usar_timing_2_4: bool = False,
    usar_filtro_regime: bool = False,
    usar_gale_1: bool = False,
    saldo_inicial: float = 1000.0,
    modo_saida: str = "FIRST_POSITIVE_PROFIT",
) -> Dict[str, Any]:
    """
    Framework determinístico de replay de ticks para Walk-Forward / Backtest fiel (Issue #14).
    Simula exatamente o pipeline:
    Tick feed -> Catalogador -> Timing24 (#13) -> Regime (#17) -> ExtremeDetector -> ReversalConfirmator -> Saída.
    Elimina fórmula sintética de P&L: utiliza payout real de contrato Deriv Turbo / Opção.
    """
    from src.core.catalogador import CatalogadorOtimizado

    cat = CatalogadorOtimizado()
    cat.ativo_selecionado = "1HZ75V"
    sm_local = MicroScalperStateMachine()

    operacoes = []
    motivos_recusa_contagem = {}
    ticks_buffer = []

    posicao_ativa = None
    lucro_acumulado = 0.0
    saldo_corrente = saldo_inicial

    # Controle de Gale 1
    recovery_level = 0
    stake_base = stake
    previous_loss = 0.0
    consecutive_losses = 0
    max_consecutive_losses = 0
    loss_streak_dist = {}

    for i, preco in enumerate(historico_ticks):
        cat.adicionar_tick(preco)
        ticks_buffer.append(preco)

        # Se temos posição aberta, avaliamos condição de saída
        if posicao_ativa is not None:
            ticks_em_posicao = i - posicao_ativa["tick_indice_entrada"]
            preco_entrada = posicao_ativa["preco_entrada"]
            direcao = posicao_ativa["tipo"]
            stake_op = posicao_ativa["stake"]

            delta = (preco - preco_entrada) if direcao == "CALL" else (preco_entrada - preco)
            delta_pct = (delta / preco_entrada) if preco_entrada > 0 else 0.0

            # Atualiza MFE e MAE da operação
            if delta_pct > posicao_ativa["mfe"]:
                posicao_ativa["mfe"] = delta_pct
            if -delta_pct > posicao_ativa["mae"]:
                posicao_ativa["mae"] = -delta_pct

            saiu = False
            motivo_saida = ""
            lucro_final = 0.0

            if modo_saida == "FIRST_POSITIVE_PROFIT":
                if delta > 0:
                    saiu = True
                    motivo_saida = "FIRST_POSITIVE_PROFIT"
                    lucro_final = round(stake_op * payout_ratio, 2)
                elif ticks_em_posicao >= max_hold_ticks:
                    saiu = True
                    motivo_saida = "MAX_HOLD_TIMEOUT"
                    lucro_final = -round(stake_op, 2)
            else:
                # Expiração no tick final do contrato (ex: 15 ticks)
                if ticks_em_posicao >= max_hold_ticks:
                    saiu = True
                    motivo_saida = "CONTRATO_EXPIRADO"
                    if delta > 0:
                        lucro_final = round(stake_op * payout_ratio, 2)
                    elif delta < 0:
                        lucro_final = -round(stake_op, 2)
                    else:
                        lucro_final = 0.0

            if saiu:
                lucro_acumulado += lucro_final
                saldo_corrente += lucro_final
                sm_local.registrar_resultado_operacao(lucro_final, motivo_saida)
                posicao_ativa["tick_indice_saida"] = i
                posicao_ativa["preco_saida"] = preco
                posicao_ativa["lucro"] = round(lucro_final, 4)
                posicao_ativa["motivo_saida"] = motivo_saida
                posicao_ativa["duracao_ticks"] = ticks_em_posicao

                if lucro_final > 0:
                    if recovery_level == 1:
                        posicao_ativa["recovery_net"] = round(lucro_final - previous_loss, 2)
                    consecutive_losses = 0
                    recovery_level = 0
                    previous_loss = 0.0
                elif lucro_final < 0:
                    consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                    loss_streak_dist[consecutive_losses] = loss_streak_dist.get(consecutive_losses, 0) + 1
                    if usar_gale_1:
                        if recovery_level == 0:
                            recovery_level = 1
                            previous_loss = abs(lucro_final)
                        else:
                            # 2 losses com Gale -> SESSION STOP
                            recovery_level = 0
                            previous_loss = 0.0

                operacoes.append(posicao_ativa)
                posicao_ativa = None

                # Verifica meta ou stop
                if meta_lucro > 0 and lucro_acumulado >= meta_lucro:
                    break
            continue

        # Se não há posição aberta, analisa oportunidade
        if i < 30:
            continue

        snapshot = cat.obter_snapshot_mercado("1HZ75V")
        analise = analisar_micro_scalping(
            dados_ou_snapshot=snapshot,
            meta=meta_lucro,
            lucro_atual=lucro_acumulado,
            modo="iniciante",
            operacoes_ativas=0,
            ultimos_ticks=ticks_buffer[-60:],
            ativo="1HZ75V",
            usar_timing_2_4=usar_timing_2_4,
            usar_filtro_regime=usar_filtro_regime,
        )

        sinal = analise.get("sinal")
        if sinal:
            # Determina stake com Gale 1 se ativo
            if usar_gale_1 and recovery_level == 1:
                stake_op = min(stake_base * 2.0, saldo_inicial * 0.02)
                tipo_rec = "GALE_1"
            else:
                stake_op = stake_base
                tipo_rec = "NORMAL"

            posicao_ativa = {
                "id": len(operacoes) + 1,
                "tipo": sinal,
                "stake": stake_op,
                "recovery_level": tipo_rec,
                "preco_entrada": preco,
                "tick_indice_entrada": i,
                "score": analise.get("score", 0.0),
                "regime": analise.get("regime", "REVERSAO_VALIDA"),
                "timestamp_simulado": i,
                "mfe": 0.0,
                "mae": 0.0,
            }
        else:
            motivo = analise.get("motivo_recusa", "Sem motivo")
            motivos_recusa_contagem[motivo] = motivos_recusa_contagem.get(motivo, 0) + 1

    total_ops = len(operacoes)
    wins = sum(1 for op in operacoes if op["lucro"] > 0)
    losses = sum(1 for op in operacoes if op["lucro"] < 0)
    empates = total_ops - wins - losses
    win_rate = (wins / total_ops * 100) if total_ops > 0 else 0.0
    loss_rate = (losses / total_ops * 100) if total_ops > 0 else 0.0

    mfes = [op.get("mfe", 0.0) for op in operacoes]
    maes = [op.get("mae", 0.0) for op in operacoes]
    mfe_medio = round(float(np.mean(mfes)), 6) if mfes else 0.0
    mae_medio = round(float(np.mean(maes)), 6) if maes else 0.0

    return {
        "total_ticks": len(historico_ticks),
        "total_operacoes": total_ops,
        "vitorias": wins,
        "derrotas": losses,
        "empates": empates,
        "win_rate_percent": round(win_rate, 2),
        "loss_rate_percent": round(loss_rate, 2),
        "maior_sequencia_perdas": max_consecutive_losses,
        "distribuicao_perdas_consecutivas": loss_streak_dist,
        "mfe_medio": mfe_medio,
        "mae_medio": mae_medio,
        "lucro_acumulado": round(lucro_acumulado, 2),
        "motivos_recusa_principais": dict(sorted(motivos_recusa_contagem.items(), key=lambda x: x[1], reverse=True)[:5]),
        "historico_operacoes": operacoes,
    }


def executar_shadow_mode(
    historico_ticks: List[float],
    ativo: str = "1HZ75V",
    stake_base: float = 0.35,
    payout_ratio: float = 0.88,
    duracao_ticks: int = 15,
    usar_timing_2_4: bool = True,
    usar_filtro_regime: bool = True,
) -> Dict[str, Any]:
    """
    Executa estratégia em modo SHADOW (Issue #19).
    Processa todos os ticks sem enviar ordens reais ou demo (REAL_ORDER_SENT=NO, BUY_SENT=0).
    Registra decisões e avalia resultado hipotético nos próximos 15 ticks.
    """
    from src.core.catalogador import CatalogadorOtimizado

    cat = CatalogadorOtimizado()
    cat.ativo_selecionado = ativo
    decisoes_shadow = []
    ticks_buffer = []

    for i, preco in enumerate(historico_ticks):
        cat.adicionar_tick(preco)
        ticks_buffer.append(preco)
        if i < 25 or i + duracao_ticks >= len(historico_ticks):
            continue

        snap = cat.obter_snapshot_mercado(ativo)
        analise = analisar_micro_scalping(
            dados_ou_snapshot=snap,
            ultimos_ticks=ticks_buffer[-60:],
            ativo=ativo,
            usar_timing_2_4=usar_timing_2_4,
            usar_filtro_regime=usar_filtro_regime,
        )

        sinal = analise.get("sinal")
        if sinal:
            ticks_futuros = historico_ticks[i + 1 : i + 1 + duracao_ticks]
            preco_entrada = preco
            preco_saida = ticks_futuros[-1]
            
            deltas = [(p - preco_entrada) if sinal == "CALL" else (preco_entrada - p) for p in ticks_futuros]
            mfe = max(deltas) / preco_entrada if preco_entrada > 0 else 0.0
            mae = max(-min(deltas), 0.0) / preco_entrada if preco_entrada > 0 else 0.0
            
            delta_final = deltas[-1]
            resultado = "WIN" if delta_final > 0 else ("LOSS" if delta_final < 0 else "EMPATE")
            lucro_teorico = round(stake_base * payout_ratio, 2) if resultado == "WIN" else (-stake_base if resultado == "LOSS" else 0.0)

            decisao = {
                "tick_indice": i,
                "ativo": ativo,
                "sinal": sinal,
                "preco_entrada": preco_entrada,
                "preco_saida": preco_saida,
                "score": analise.get("score", 0.0),
                "regime": analise.get("regime", "REVERSAO_VALIDA"),
                "timing_2_4": analise.get("timing_2_4", {}),
                "resultado": resultado,
                "lucro_teorico": lucro_teorico,
                "mfe": round(mfe, 6),
                "mae": round(mae, 6),
            }
            decisoes_shadow.append(decisao)

    total = len(decisoes_shadow)
    wins = sum(1 for d in decisoes_shadow if d["resultado"] == "WIN")
    losses = sum(1 for d in decisoes_shadow if d["resultado"] == "LOSS")
    empates = total - wins - losses
    win_rate = (wins / total * 100) if total > 0 else 0.0

    return {
        "modo": "SHADOW",
        "ativo": ativo,
        "total_decisoes": total,
        "vitorias_teoricas": wins,
        "derrotas_teoricas": losses,
        "empates_teoricos": empates,
        "win_rate_teorico": round(win_rate, 2),
        "decisoes": decisoes_shadow,
    }


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
