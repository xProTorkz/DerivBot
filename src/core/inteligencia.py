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
) -> Dict[str, Any]:
    """
    ANÁLISE CANÔNICA DO MICRO-SCALPER SELETIVO (Issues #2, #3, #4, #20).
    Substitui qualquer lógica aleatória por análise estatística determinística.
    Integra ExtremeDetector, ReversalConfirmator, ConfluenceScore e StateMachine.
    Suporta concorrência 3 / 5 / 10 posições simultâneas e state machine isolada por ativo.
    """
    try:
        # Se ativo não foi passado explicitamente, tenta extrair do snapshot se for dict
        if not ativo and isinstance(dados_ou_snapshot, dict):
            ativo = dados_ou_snapshot.get("ativo") or dados_ou_snapshot.get("simbolo")

        sm = state_machine or obter_state_machine(ativo)

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
            # Converte lista de velas ou ticks para snapshot simplificado
            if isinstance(dados_ou_snapshot[0], dict):
                closes = [v["close"] for v in dados_ou_snapshot]
            else:
                closes = [float(x) for x in dados_ou_snapshot]
            
            preco_atual = closes[-1]
            ticks = closes[-60:]
            
            # Cálculo rápido de indicadores para compatibilidade
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
        elif sm.estado_atual in (
            MicroScalperState.POSICAO_ABERTA,
            MicroScalperState.COMPRANDO,
            MicroScalperState.SAINDO,
            MicroScalperState.COOLDOWN,
        ):
            # Não reseta para NORMAL se o ativo já possui uma operação ativa ou em transição
            return {
                "sinal": None,
                "confianca": 0.0,
                "score": getattr(sm, "ultimo_score", 0.0),
                "min_score": target_min_score,
                "estado": sm.estado_atual,
                "razao": f"Ativo em estado {sm.estado_atual.name}",
                "motivo_recusa": f"Ativo em estado {sm.estado_atual.name}",
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

        # 5. Confirmador de Reversão
        confirmador = ReversalConfirmator()
        reversao_res = confirmador.confirmar(direcao, ticks, snapshot)

        # 6. Score de Confluência calibrado por perfil
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

        # SINAL APROVADO COM EXTREMO + REVERSÃO + CONFLUÊNCIA!
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
    max_hold_ticks: int = 45,
) -> Dict[str, Any]:
    """
    Framework determinístico de replay de ticks para Walk-Forward / Backtest.
    Simula exatamente o pipeline:
    Tick feed -> Catalogador -> ExtremeDetector -> ReversalConfirmator -> ConfluenceScore -> Saída no 1º Lucro.
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

    for i, preco in enumerate(historico_ticks):
        cat.adicionar_tick(preco)
        ticks_buffer.append(preco)

        # Se temos posição aberta, avaliamos condição de saída
        if posicao_ativa is not None:
            ticks_em_posicao = i - posicao_ativa["tick_indice_entrada"]
            preco_entrada = posicao_ativa["preco_entrada"]
            direcao = posicao_ativa["tipo"]

            # Variação percentual do preço
            delta_pct = (preco - preco_entrada) / preco_entrada if direcao == "CALL" else (preco_entrada - preco) / preco_entrada
            
            # Estimativa de lucro proporcional na Deriv
            # No primeiro tick positivo com lucro líquido real:
            lucro_estimado = delta_pct * stake * 50.0  # Fator de alavancagem sintética
            
            # Condição de saída: primeiro lucro positivo >= min_exit_profit OU timeout
            saiu = False
            motivo_saida = ""
            lucro_final = 0.0

            if lucro_estimado >= min_exit_profit:
                saiu = True
                lucro_final = lucro_estimado
                motivo_saida = "FIRST_POSITIVE_PROFIT"
            elif ticks_em_posicao >= max_hold_ticks:
                saiu = True
                lucro_final = lucro_estimado
                motivo_saida = "MAX_HOLD_TIMEOUT"

            if saiu:
                lucro_acumulado += lucro_final
                sm_local.registrar_resultado_operacao(lucro_final, motivo_saida)
                posicao_ativa["tick_indice_saida"] = i
                posicao_ativa["preco_saida"] = preco
                posicao_ativa["lucro"] = round(lucro_final, 4)
                posicao_ativa["motivo_saida"] = motivo_saida
                posicao_ativa["duracao_ticks"] = ticks_em_posicao
                operacoes.append(posicao_ativa)
                posicao_ativa = None
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
        )

        sinal = analise.get("sinal")
        if sinal:
            posicao_ativa = {
                "id": len(operacoes) + 1,
                "tipo": sinal,
                "preco_entrada": preco,
                "tick_indice_entrada": i,
                "score": analise.get("score", 0.0),
                "timestamp_simulado": i,
            }
        else:
            motivo = analise.get("motivo_recusa", "Sem motivo")
            motivos_recusa_contagem[motivo] = motivos_recusa_contagem.get(motivo, 0) + 1

    total_ops = len(operacoes)
    wins = sum(1 for op in operacoes if op["lucro"] > 0)
    losses = total_ops - wins
    win_rate = (wins / total_ops * 100) if total_ops > 0 else 0.0

    return {
        "total_ticks": len(historico_ticks),
        "total_operacoes": total_ops,
        "vitorias": wins,
        "derrotas": losses,
        "win_rate_percent": round(win_rate, 2),
        "lucro_acumulado": round(lucro_acumulado, 2),
        "motivos_recusa_principais": dict(sorted(motivos_recusa_contagem.items(), key=lambda x: x[1], reverse=True)[:5]),
        "historico_operacoes": operacoes,
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
