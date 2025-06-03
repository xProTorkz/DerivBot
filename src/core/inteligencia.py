import json
import os
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
import logging
from src import config

# Diretório para armazenar os dados de memória
MEMORIA_DIR = "memoria"


def _criar_diretorio_memoria():
    """Cria o diretório de memória se não existir"""
    if not os.path.exists(MEMORIA_DIR):
        os.makedirs(MEMORIA_DIR)


def _obter_arquivo_memoria(cliente_id: str) -> str:
    """Retorna o caminho do arquivo de memória para um cliente"""
    return os.path.join(MEMORIA_DIR, f"{cliente_id}.json")


def carregar_memoria(cliente_id: str) -> Dict[str, Any]:
    """
    Carrega os dados de memória de um cliente
    Args:
        cliente_id: Identificador do cliente
    Returns:
        Dicionário com os dados de memória
    """
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
        print(f"Erro ao carregar memória: {e}")
        return {
            "historico": [],
            "ultima_atualizacao": datetime.now().isoformat(),
            "estatisticas": {
                "total_operacoes": 0,
                "lucro_total": 0.0,
                "assertividade": 0.0,
            },
        }


def salvar_memoria(cliente_id: str, dados: Dict[str, Any]) -> bool:
    """
    Salva os dados de memória de um cliente
    Args:
        cliente_id: Identificador do cliente
        dados: Dicionário com os dados a serem salvos
    Returns:
        True se salvou com sucesso, False caso contrário
    """
    try:
        _criar_diretorio_memoria()
        arquivo = _obter_arquivo_memoria(cliente_id)

        # Carrega dados existentes
        dados_existentes = carregar_memoria(cliente_id)

        # Atualiza dados
        dados_existentes["historico"].append(dados)
        dados_existentes["ultima_atualizacao"] = datetime.now().isoformat()

        # Atualiza estatísticas
        historico = dados_existentes["historico"]
        total_ops = len(historico)
        lucro_total = sum(op.get("lucro", 0) for op in historico)
        ops_lucro = sum(1 for op in historico if op.get("lucro", 0) > 0)

        dados_existentes["estatisticas"] = {
            "total_operacoes": total_ops,
            "lucro_total": lucro_total,
            "assertividade": (ops_lucro / total_ops * 100) if total_ops > 0 else 0,
        }

        # Salva dados atualizados
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(dados_existentes, f, indent=4, ensure_ascii=False)

        return True

    except Exception as e:
        print(f"Erro ao salvar memória: {e}")
        return False


def limpar_memoria(cliente_id: str) -> bool:
    """
    Limpa os dados de memória de um cliente
    Args:
        cliente_id: Identificador do cliente
    Returns:
        True se limpou com sucesso, False caso contrário
    """
    try:
        arquivo = _obter_arquivo_memoria(cliente_id)
        if os.path.exists(arquivo):
            os.remove(arquivo)
        return True
    except Exception as e:
        print(f"Erro ao limpar memória: {e}")
        return False


# =================== NOVAS FUNÇÕES PARA SUPORTE E RESISTÊNCIA ===================


def detectar_suporte_resistencia(
    velas: List[Dict], janela: int = 5
) -> Tuple[List[float], List[float]]:
    """
    Detecta níveis de suporte e resistência usando método de máximos e mínimos locais

    Args:
        velas: Lista de velas OHLCV
        janela: Tamanho da janela para detectar máximos e mínimos locais

    Returns:
        Tuple contendo (suportes, resistências)
    """
    try:
        # Verifica se há dados suficientes
        if len(velas) < janela * 2:
            return [], []

        # Extrai preços de fechamento
        closes = [v["close"] for v in velas]
        highs = [v["high"] for v in velas]
        lows = [v["low"] for v in velas]

        # Lista para armazenar suportes e resistências
        suportes = []
        resistencias = []

        # Detecta suportes (mínimos locais)
        for i in range(janela, len(lows) - janela):
            # Verifica se é um mínimo local
            if all(lows[i] <= lows[i - j] for j in range(1, janela + 1)) and all(
                lows[i] <= lows[i + j] for j in range(1, janela + 1)
            ):
                suportes.append(lows[i])

        # Detecta resistências (máximos locais)
        for i in range(janela, len(highs) - janela):
            # Verifica se é um máximo local
            if all(highs[i] >= highs[i - j] for j in range(1, janela + 1)) and all(
                highs[i] >= highs[i + j] for j in range(1, janela + 1)
            ):
                resistencias.append(highs[i])

        # Filtra níveis próximos (agrupa níveis semelhantes)
        if suportes:
            suportes = agrupar_niveis_proximos(suportes)
        if resistencias:
            resistencias = agrupar_niveis_proximos(resistencias)

        return suportes, resistencias

    except Exception as e:
        print(f"Erro ao detectar suporte/resistência: {e}")
        return [], []


def agrupar_niveis_proximos(
    niveis: List[float], threshold_percent: float = 0.05
) -> List[float]:
    """
    Agrupa níveis que estão muito próximos um do outro

    Args:
        niveis: Lista de níveis de preço
        threshold_percent: Porcentagem de proximidade para considerar como mesmo nível

    Returns:
        Lista de níveis filtrados
    """
    if not niveis:
        return []

    # Ordena os níveis
    niveis_ordenados = sorted(niveis)

    # Lista para armazenar os níveis agrupados
    niveis_agrupados = []

    # Grupo atual
    grupo_atual = [niveis_ordenados[0]]

    # Para cada nível, verifica se está próximo ao grupo atual
    for i in range(1, len(niveis_ordenados)):
        nivel_atual = niveis_ordenados[i]
        nivel_referencia = grupo_atual[0]

        # Calcula a diferença percentual
        diff_percent = abs(nivel_atual - nivel_referencia) / nivel_referencia

        # Se estiver dentro do threshold, adiciona ao grupo atual
        if diff_percent <= threshold_percent:
            grupo_atual.append(nivel_atual)
        else:
            # Adiciona a média do grupo atual e começa um novo grupo
            niveis_agrupados.append(sum(grupo_atual) / len(grupo_atual))
            grupo_atual = [nivel_atual]

    # Adiciona o último grupo
    if grupo_atual:
        niveis_agrupados.append(sum(grupo_atual) / len(grupo_atual))

    return niveis_agrupados


def esta_em_suporte(
    preco_atual: float, suportes: List[float], margem_percent: float = 0.1
) -> bool:
    """
    Verifica se o preço atual está em uma zona de suporte

    Args:
        preco_atual: Preço atual
        suportes: Lista de níveis de suporte
        margem_percent: Margem percentual para considerar que está no suporte

    Returns:
        True se estiver próximo a um suporte, False caso contrário
    """
    if not suportes:
        return False

    for suporte in suportes:
        margem = suporte * margem_percent
        if abs(preco_atual - suporte) <= margem:
            return True

    return False


def esta_em_resistencia(
    preco_atual: float, resistencias: List[float], margem_percent: float = 0.1
) -> bool:
    """
    Verifica se o preço atual está em uma zona de resistência

    Args:
        preco_atual: Preço atual
        resistencias: Lista de níveis de resistência
        margem_percent: Margem percentual para considerar que está na resistência

    Returns:
        True se estiver próximo a uma resistência, False caso contrário
    """
    if not resistencias:
        return False

    for resistencia in resistencias:
        margem = resistencia * margem_percent
        if abs(preco_atual - resistencia) <= margem:
            return True

    return False


def analisar_micro_scalping(
    velas: List[Dict],
    meta: float,
    lucro_atual: float,
    modo: str,
    operacoes_ativas: int = 0,
    max_operacoes: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Analisa oportunidades de micro scalping com foco em suporte e resistência
    para ativos de 1 segundo.

    Args:
        velas: Lista de velas OHLCV
        meta: Meta de lucro para a sessão
        lucro_atual: Lucro atual da sessão
        modo: Modo de operação ('iniciante', 'conservador', 'agressivo')
        operacoes_ativas: Número de operações ativas
        max_operacoes: Número máximo de operações simultâneas permitidas

    Returns:
        Dicionário com decisão e análise
    """
    try:
        # Verificações iniciais
        if len(velas) < 20:
            return {"sinal": None, "confianca": 0.0, "razao": "Dados insuficientes"}

        # Define máximo de operações por modo
        if max_operacoes is None:
            if modo == "iniciante":
                max_operacoes = 1
            elif modo == "conservador":
                max_operacoes = 3
            else:  # agressivo
                max_operacoes = 5

        # Se já atingiu o máximo de operações para o modo, aguarda
        if operacoes_ativas >= max_operacoes:
            return {
                "sinal": None,
                "confianca": 0.0,
                "razao": f"Máximo de operações atingido ({operacoes_ativas}/{max_operacoes})",
            }

        # Verifica proximidade da meta
        meta_atingida_percent = (lucro_atual / meta) * 100
        if meta_atingida_percent > 75:
            # Reduzir número máximo de operações quando próximo da meta
            new_max_ops = max(1, int(max_operacoes * (1 - meta_atingida_percent / 100)))
            if operacoes_ativas >= new_max_ops:
                return {
                    "sinal": None,
                    "confianca": 0.0,
                    "razao": f"Próximo da meta ({meta_atingida_percent:.1f}%). Limitando operações a {new_max_ops}",
                }

        # Analisa RSI para confirmar sobrecompra/sobrevenda
        closes = [v["close"] for v in velas]
        rsi = calcular_rsi(closes)

        # Detecta suportes e resistências
        suportes, resistencias = detectar_suporte_resistencia(velas)

        # Preço atual e direção recente (tendência de curtíssimo prazo)
        preco_atual = velas[-1]["close"]
        direcao_curta = "ALTA" if velas[-1]["close"] > velas[-3]["close"] else "BAIXA"

        # Análise de força da tendência
        forca_tendencia = (
            abs(velas[-1]["close"] - velas[-5]["close"]) / velas[-5]["close"] * 100
        )

        # Volatilidade recente
        volatilidade = np.std([v["close"] for v in velas[-10:]])

        # Lógica de decisão para scalping
        decisao = None
        confianca = 0.0
        razao = ""

        # --- Otimização Modo Iniciante: Requerer confiança altíssima e condições mais estritas ---
        confianca_minima_iniciante = 0.95  # Exigência de confiança muito alta
        rsi_sobrecompra_iniciante = 75
        rsi_sobrevenda_iniciante = 25
        margem_sr_iniciante = 0.02  # Margem mais estreita para S/R

        # Verifica se está em suporte ou resistência (com critérios mais rígidos para iniciante)
        if modo == "iniciante":
            if (
                esta_em_resistencia(preco_atual, resistencias, margem_sr_iniciante)
                and rsi > rsi_sobrecompra_iniciante
            ):
                decisao = "venda"
                confianca = min(
                    0.9 + (rsi - rsi_sobrecompra_iniciante) / 50, 0.99
                )  # Confiança alta, mas limitada
                razao = f"[INICIANTE] Resistência ({preco_atual:.5f}) + RSI extremo ({rsi:.1f})"
            elif (
                esta_em_suporte(preco_atual, suportes, margem_sr_iniciante)
                and rsi < rsi_sobrevenda_iniciante
            ):
                decisao = "compra"
                confianca = min(
                    0.9 + (rsi_sobrevenda_iniciante - rsi) / 50, 0.99
                )  # Confiança alta, mas limitada
                razao = (
                    f"[INICIANTE] Suporte ({preco_atual:.5f}) + RSI extremo ({rsi:.1f})"
                )

            # Se for iniciante e a confiança não atingir o mínimo, não opera
            if decisao and confianca < confianca_minima_iniciante:
                razao += f" (Confiança {confianca:.2f} < {confianca_minima_iniciante} - Aguardando)"
                decisao = None
                confianca = 0.0

        # --- Lógica para outros modos (Conservador/Agressivo) ---
        elif modo != "iniciante":  # Aplica a lógica original para outros modos
            if esta_em_resistencia(preco_atual, resistencias, 0.03) and rsi > 70:
                decisao = "venda"
                confianca = min(0.8 + (rsi - 70) / 100, 0.98)
                razao = f"Resistência encontrada em {preco_atual:.5f} com RSI alto ({rsi:.1f})"

            elif esta_em_suporte(preco_atual, suportes, 0.03) and rsi < 30:
                decisao = "compra"
                confianca = min(0.8 + (30 - rsi) / 100, 0.98)
                razao = (
                    f"Suporte encontrado em {preco_atual:.5f} com RSI baixo ({rsi:.1f})"
                )

            # Adiciona novas condições para tendências claras
            # Tendência de alta forte com confirmação
            elif (
                direcao_curta == "ALTA"
                and forca_tendencia > 0.15
                and rsi > 40
                and rsi < 65
            ):
                # Verifica se temos 3 velas consecutivas de alta
                if (
                    velas[-1]["close"] > velas[-1]["open"]
                    and velas[-2]["close"] > velas[-2]["open"]
                    and velas[-3]["close"] > velas[-3]["open"]
                ):
                    decisao = "compra"
                    confianca = 0.65 + min(forca_tendencia / 100, 0.25)
                    razao = f"Tendência de alta confirmada com força {forca_tendencia:.2f}%, RSI={rsi:.1f}"

            # Tendência de baixa forte com confirmação
            elif (
                direcao_curta == "BAIXA"
                and forca_tendencia > 0.15
                and rsi < 60
                and rsi > 35
            ):
                # Verifica se temos 3 velas consecutivas de baixa
                if (
                    velas[-1]["close"] < velas[-1]["open"]
                    and velas[-2]["close"] < velas[-2]["open"]
                    and velas[-3]["close"] < velas[-3]["open"]
                ):
                    decisao = "venda"
                    confianca = 0.65 + min(forca_tendencia / 100, 0.25)
                    razao = f"Tendência de baixa confirmada com força {forca_tendencia:.2f}%, RSI={rsi:.1f}"

            # Reversão de tendência em zona neutra
            elif abs(rsi - 50) < 10 and volatilidade > 0:
                # Detecta uma reversão recente
                if (
                    velas[-1]["close"] > velas[-1]["open"]
                    and velas[-2]["close"] < velas[-2]["open"]
                    and velas[-3]["close"] < velas[-3]["open"]
                ):
                    decisao = "compra"
                    confianca = 0.62
                    razao = (
                        f"Possível reversão de baixa para alta detectada, RSI={rsi:.1f}"
                    )
                elif (
                    velas[-1]["close"] < velas[-1]["open"]
                    and velas[-2]["close"] > velas[-2]["open"]
                    and velas[-3]["close"] > velas[-3]["open"]
                ):
                    decisao = "venda"
                    confianca = 0.62
                    razao = (
                        f"Possível reversão de alta para baixa detectada, RSI={rsi:.1f}"
                    )

        # Resultado final
        resultado = {
            "sinal": decisao,
            "confianca": confianca,
            "razao": razao,
            "analise": {
                "preco": preco_atual,
                "rsi": rsi,
                "direcao": direcao_curta,
                "forca_tendencia": forca_tendencia,
                "volatilidade": volatilidade,
                "suportes": suportes[-3:] if suportes else [],
                "resistencias": resistencias[-3:] if resistencias else [],
                "meta_progresso": meta_atingida_percent,
            },
        }

        return resultado

    except Exception as e:
        print(f"Erro na análise de micro scalping: {e}")
        return {"sinal": None, "confianca": 0.0, "razao": f"Erro: {str(e)}"}


def calcular_rsi(precos: List[float], periodo: int = 14) -> float:
    """
    Calcula o Índice de Força Relativa (RSI)

    Args:
        precos: Lista de preços de fechamento
        periodo: Período para cálculo do RSI

    Returns:
        Valor do RSI (0-100)
    """
    if len(precos) < periodo + 1:
        return 50.0  # valor neutro para dados insuficientes

    # Calcula as diferenças entre preços consecutivos
    deltas = np.diff(precos)

    # Separa ganhos e perdas
    seed = deltas[: periodo + 1]
    ganhos = seed.copy()
    perdas = seed.copy()
    ganhos[seed < 0] = 0
    perdas[seed > 0] = 0
    perdas = abs(perdas)

    # Calcula médias de ganhos e perdas
    avg_ganho = np.mean(ganhos[:periodo])
    avg_perda = np.mean(perdas[:periodo])

    if avg_perda == 0:
        return 100.0

    rs = avg_ganho / avg_perda
    rsi = 100 - (100 / (1 + rs))

    return rsi


class Inteligencia:
    def __init__(self):
        self.logger = logging.getLogger("Inteligencia")
        self.cache = {}
        self.ultima_analise = None

    def analisar_mercado(self, dados: List[Dict]) -> Dict:
        """Analisa dados de mercado e retorna previsão"""
        try:
            # Converte dados para DataFrame
            df = pd.DataFrame(dados)

            # Calcula indicadores técnicos
            indicadores = self._calcular_indicadores(df)

            # Gera previsão
            previsao = self._gerar_previsao(indicadores)

            # Atualiza cache
            self.cache["ultima_analise"] = {
                "timestamp": datetime.now().isoformat(),
                "indicadores": indicadores,
                "previsao": previsao,
            }

            return previsao

        except Exception as e:
            self.logger.error(f"Erro na análise: {str(e)}")
            return {"direcao": "neutro", "confianca": 0.0, "indicadores": {}}

    def _calcular_indicadores(self, df: pd.DataFrame) -> Dict:
        """Calcula indicadores técnicos"""
        indicadores = {}

        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        indicadores["rsi"] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = df["close"].ewm(span=12, adjust=False).mean()
        exp2 = df["close"].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        indicadores["macd"] = macd
        indicadores["macd_signal"] = signal

        # Bollinger Bands
        sma = df["close"].rolling(window=20).mean()
        std = df["close"].rolling(window=20).std()
        indicadores["bb_upper"] = sma + (std * 2)
        indicadores["bb_lower"] = sma - (std * 2)

        # Moving Averages
        indicadores["sma_20"] = df["close"].rolling(window=20).mean()
        indicadores["sma_50"] = df["close"].rolling(window=50).mean()
        indicadores["sma_200"] = df["close"].rolling(window=200).mean()

        return indicadores

    def _gerar_previsao(self, indicadores: Dict) -> Dict:
        """Gera previsão baseada nos indicadores"""
        # Inicializa contadores
        sinais_compra = 0
        sinais_venda = 0
        total_sinais = 0

        # Analisa RSI
        rsi = indicadores["rsi"].iloc[-1]
        if rsi < 30:
            sinais_compra += 1
        elif rsi > 70:
            sinais_venda += 1
        total_sinais += 1

        # Analisa MACD
        macd = indicadores["macd"].iloc[-1]
        signal = indicadores["macd_signal"].iloc[-1]
        if macd > signal:
            sinais_compra += 1
        elif macd < signal:
            sinais_venda += 1
        total_sinais += 1

        # Analisa Bollinger Bands
        preco = indicadores["sma_20"].iloc[-1]
        bb_upper = indicadores["bb_upper"].iloc[-1]
        bb_lower = indicadores["bb_lower"].iloc[-1]
        if preco < bb_lower:
            sinais_compra += 1
        elif preco > bb_upper:
            sinais_venda += 1
        total_sinais += 1

        # Analisa Moving Averages
        sma_20 = indicadores["sma_20"].iloc[-1]
        sma_50 = indicadores["sma_50"].iloc[-1]
        sma_200 = indicadores["sma_200"].iloc[-1]

        if sma_20 > sma_50 and sma_50 > sma_200:
            sinais_compra += 1
        elif sma_20 < sma_50 and sma_50 < sma_200:
            sinais_venda += 1
        total_sinais += 1

        # Calcula confiança
        confianca_compra = sinais_compra / total_sinais
        confianca_venda = sinais_venda / total_sinais

        # Define direção e confiança
        if confianca_compra > confianca_venda:
            direcao = "compra"
            confianca = confianca_compra
        elif confianca_venda > confianca_compra:
            direcao = "venda"
            confianca = confianca_venda
        else:
            direcao = "neutro"
            confianca = 0.5

        return {
            "direcao": direcao,
            "confianca": confianca,
            "indicadores": {
                "rsi": float(rsi),
                "macd": float(macd),
                "bb_upper": float(bb_upper),
                "bb_lower": float(bb_lower),
                "sma_20": float(sma_20),
                "sma_50": float(sma_50),
                "sma_200": float(sma_200),
            },
        }

    def get_ultima_analise(self) -> Optional[Dict]:
        """Retorna última análise realizada"""
        return self.cache.get("ultima_analise")

    def limpar_cache(self):
        """Limpa cache de análises"""
        self.cache = {}
        self.ultima_analise = None


# Instância global da inteligência
inteligencia = Inteligencia()
