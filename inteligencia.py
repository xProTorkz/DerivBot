import json
import os
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

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

        # Verifica se está em suporte ou resistência
        if esta_em_resistencia(preco_atual, resistencias, 0.03) and rsi > 70:
            decisao = "venda"
            confianca = min(0.7 + (rsi - 70) / 100, 0.95)
            razao = (
                f"Resistência encontrada em {preco_atual:.5f} com RSI alto ({rsi:.1f})"
            )

        elif esta_em_suporte(preco_atual, suportes, 0.03) and rsi < 30:
            decisao = "compra"
            confianca = min(0.7 + (30 - rsi) / 100, 0.95)
            razao = f"Suporte encontrado em {preco_atual:.5f} com RSI baixo ({rsi:.1f})"

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
