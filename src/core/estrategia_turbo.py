"""
ESTRATÉGIA TURBO SCALPING - 15 SEGUNDOS
Configurações específicas para estratégia turbo com VIX75/VIX100
"""

# ESTRATÉGIA FIXA TURBO SCALPING - 15 SEGUNDOS
ESTRATEGIA_TURBO = {
    "nome": "Turbo Scalping 15s",
    "descricao": "Estratégia fixa com contratos de 15 segundos em VIX75/VIX100",
    "timeframe": "15s",
    "duracao_contrato": 15,  # 15 segundos
    # ATIVOS PRIORITÁRIOS
    "ativos_principais": ["1HZ75V", "1HZ100V"],  # VIX75 e VIX100
    "ativos_backup": ["R_75", "R_100"],  # Backup se VIX não disponível
    # INDICADORES TÉCNICOS
    "indicadores": {
        "ema_rapida": 8,  # EMA rápida
        "ema_lenta": 21,  # EMA lenta
        "rsi_periodo": 14,  # RSI
        "rsi_sobrecompra": 70,
        "rsi_sobrevenda": 30,
        "bollinger_periodo": 20,
        "bollinger_desvio": 2,
    },
    # GESTÃO DE RISCO
    "gestao_risco": {
        "stop_loss": 2.0,  # 2% máximo de perda por operação
        "take_profit": 5.0,  # 5% de lucro alvo
        "martingale_max": 2,  # Máximo 2 níveis de martingale
        "martingale_fator": 2.0,  # Multiplicador do martingale
        "max_operacoes_dia": 50,  # Máximo de operações por dia
        "pausa_entre_operacoes": 1,  # 1 vela de pausa entre operações
    },
    # CONFIGURAÇÕES DE ENTRADA
    "entrada": {
        "confirmacao_necessaria": True,  # Precisa de confirmação de múltiplos indicadores
        "min_confianca": 0.85,  # Confiança mínima para entrada
        "volume_inicial": 0.35,  # Volume inicial mínimo
        "volume_maximo": 10.0,  # Volume máximo por operação
    },
    # REGRAS DE ENTRADA
    "regras_entrada": {
        "call": {
            "ema_cruzamento": "ema8 > ema21",
            "rsi_condicao": "rsi < 70",
            "bollinger_condicao": "preco toca banda inferior ou está próximo",
            "confirmacao": "todos os sinais devem estar alinhados",
        },
        "put": {
            "ema_cruzamento": "ema8 < ema21",
            "rsi_condicao": "rsi > 30",
            "bollinger_condicao": "preco toca banda superior ou está próximo",
            "confirmacao": "todos os sinais devem estar alinhados",
        },
    },
}

# CONFIGURAÇÕES ESPECÍFICAS POR ATIVO
ATIVOS_TURBO = {
    "1HZ75V": {  # Volatility 75 Index
        "nome": "Volatility 75 Index",
        "simbolo_deriv": "1HZ75V",
        "min_stake": 0.35,
        "max_stake": 10.0,
        "contract_types": ["CALL", "PUT"],
        "duracao": 15,  # 15 segundos
        "tipo_contrato": "turbo",
        "prioridade": 1,  # Máxima prioridade
        "timeframe_analise": "15s",
        "volatilidade": "alta",
        "spread": "baixo",
        "horario": "24/7",
        "gestao_especifica": {
            "stop_loss": 2.0,
            "take_profit": 5.0,
            "martingale_max": 2,
        },
    },
    "1HZ100V": {  # Volatility 100 Index
        "nome": "Volatility 100 Index",
        "simbolo_deriv": "1HZ100V",
        "min_stake": 0.35,
        "max_stake": 10.0,
        "contract_types": ["CALL", "PUT"],
        "duracao": 15,
        "tipo_contrato": "turbo",
        "prioridade": 2,
        "timeframe_analise": "15s",
        "volatilidade": "muito_alta",
        "spread": "baixo",
        "horario": "24/7",
        "gestao_especifica": {
            "stop_loss": 2.0,
            "take_profit": 4.5,  # Ligeiramente menor devido à maior volatilidade
            "martingale_max": 2,
        },
    },
    # BACKUP - Multipliers se turbo não disponível
    "R_75": {
        "nome": "Volatility 75 Index (Multiplier)",
        "simbolo_deriv": "R_75",
        "min_stake": 0.35,
        "max_stake": 5.0,
        "contract_types": ["MULTUP", "MULTDOWN"],
        "multipliers": [1, 2, 3, 4, 5],
        "duracao": 15,
        "tipo_contrato": "multiplier",
        "prioridade": 3,
        "timeframe_analise": "15s",
        "gestao_especifica": {
            "stop_loss": 2.0,
            "take_profit": 4.0,
            "martingale_max": 2,
        },
    },
    "R_100": {
        "nome": "Volatility 100 Index (Multiplier)",
        "simbolo_deriv": "R_100",
        "min_stake": 0.35,
        "max_stake": 5.0,
        "contract_types": ["MULTUP", "MULTDOWN"],
        "multipliers": [1, 2, 3, 4, 5],
        "duracao": 15,
        "tipo_contrato": "multiplier",
        "prioridade": 4,
        "timeframe_analise": "15s",
        "gestao_especifica": {
            "stop_loss": 2.0,
            "take_profit": 4.0,
            "martingale_max": 2,
        },
    },
}

# CONFIGURAÇÕES DE ANÁLISE TÉCNICA
ANALISE_TECNICA = {
    "timeframe_principal": "15s",
    "velas_historico": 50,  # Número de velas para análise
    "indicadores_obrigatorios": ["EMA", "RSI", "BOLLINGER"],
    "peso_indicadores": {
        "ema_cruzamento": 0.4,  # 40% do peso da decisão
        "rsi_nivel": 0.3,  # 30% do peso
        "bollinger_toque": 0.3,  # 30% do peso
    },
    "filtros_entrada": {
        "volatilidade_min": 0.1,  # Volatilidade mínima para entrada
        "volume_min": 100,  # Volume mínimo
        "spread_max": 0.5,  # Spread máximo aceitável
    },
}

# CONFIGURAÇÕES DE EXECUÇÃO
EXECUCAO = {
    "modo_execucao": "automatico",
    "confirmacao_manual": False,  # Execução totalmente automática
    "timeout_entrada": 3,  # 3 segundos para executar entrada
    "timeout_saida": 1,  # 1 segundo para executar saída
    "retry_max": 3,  # Máximo 3 tentativas de execução
    "intervalo_retry": 0.5,  # 0.5s entre tentativas
}

# CONFIGURAÇÕES DE MONITORAMENTO
MONITORAMENTO = {
    "logs_detalhados": True,
    "salvar_historico": True,
    "alertas_telegram": False,  # Desabilitado por padrão
    "metricas_tempo_real": True,
    "backup_dados": True,
}


def obter_ativo_prioritario():
    """Retorna o ativo com maior prioridade disponível"""
    ativos_ordenados = sorted(ATIVOS_TURBO.items(), key=lambda x: x[1]["prioridade"])
    return ativos_ordenados[0][0]  # Retorna o símbolo do ativo


def validar_entrada(ativo, sinal, confianca, indicadores):
    """Valida se uma entrada é válida segundo a estratégia"""
    config_ativo = ATIVOS_TURBO.get(ativo)
    if not config_ativo:
        return False, "Ativo não configurado para estratégia turbo"

    # Verifica confiança mínima
    if confianca < ESTRATEGIA_TURBO["entrada"]["min_confianca"]:
        return (
            False,
            f"Confiança {confianca:.2f} abaixo do mínimo {ESTRATEGIA_TURBO['entrada']['min_confianca']}",
        )

    # Verifica indicadores obrigatórios
    indicadores_necessarios = ANALISE_TECNICA["indicadores_obrigatorios"]
    for indicador in indicadores_necessarios:
        if indicador not in indicadores:
            return False, f"Indicador {indicador} não fornecido"

    return True, "Entrada válida"


def calcular_volume_entrada(saldo_atual, modo_operacao, nivel_martingale=0):
    """Calcula o volume ideal para entrada"""
    config_entrada = ESTRATEGIA_TURBO["entrada"]

    # Volume base baseado no modo
    volumes_base = {"iniciante": 0.35, "conservador": 0.50, "agressivo": 1.00}

    volume_base = volumes_base.get(modo_operacao, 0.35)

    # Aplica martingale se necessário
    if nivel_martingale > 0:
        fator_martingale = ESTRATEGIA_TURBO["gestao_risco"]["martingale_fator"]
        volume_base *= fator_martingale**nivel_martingale

    # Limita ao máximo configurado
    volume_max = min(
        config_entrada["volume_maximo"], saldo_atual * 0.02
    )  # Máximo 2% do saldo
    volume_final = min(volume_base, volume_max)

    # Garante mínimo
    volume_final = max(volume_final, config_entrada["volume_inicial"])

    return round(volume_final, 2)


def analisar_entrada_turbo(
    ativo, preco_atual, modo, meta, lucro_atual, operacoes_ativas
):
    """
    ANÁLISE PRINCIPAL DA ESTRATÉGIA TURBO
    Retorna análise completa para entrada em contratos de 15 segundos
    """
    import random
    import time

    # Força uso do VIX75 se não for o ativo atual
    if ativo != "1HZ75V":
        ativo = "1HZ75V"

    # Configurações da estratégia
    config = ESTRATEGIA_TURBO
    config_ativo = ATIVOS_TURBO.get(ativo, ATIVOS_TURBO["1HZ75V"])

    # Verifica se deve operar
    if operacoes_ativas >= 3:  # Máximo 3 operações simultâneas
        return {
            "executada": False,
            "razao": "Limite de operações simultâneas atingido (3)",
            "confianca": 0.0,
            "lucro_atual": lucro_atual,
            "operacoes_ativas": operacoes_ativas,
        }

    # Verifica se atingiu meta
    if lucro_atual >= meta:
        return {
            "executada": False,
            "razao": f"Meta diária de ${meta:.2f} já atingida",
            "confianca": 0.0,
            "lucro_atual": lucro_atual,
            "operacoes_ativas": operacoes_ativas,
        }

    # SIMULAÇÃO DE ANÁLISE TÉCNICA TURBO
    # Em uma implementação real, aqui seria feita análise de EMA, RSI, Bollinger

    # Simula indicadores técnicos
    ema8 = preco_atual * (1 + random.uniform(-0.001, 0.001))
    ema21 = preco_atual * (1 + random.uniform(-0.002, 0.002))
    rsi = random.uniform(25, 75)
    bb_superior = preco_atual * 1.002
    bb_inferior = preco_atual * 0.998

    # Análise de tendência
    tendencia_alta = ema8 > ema21
    rsi_neutro = 30 < rsi < 70
    preco_na_banda = (preco_atual <= bb_inferior) or (preco_atual >= bb_superior)

    # Calcula confiança baseada nos indicadores
    confianca = 0.0
    sinais = []

    # Sinal de CALL (alta)
    if tendencia_alta and rsi < 65 and preco_atual <= bb_inferior:
        confianca = random.uniform(0.85, 0.95)
        tipo_operacao = "CALL"
        sinais.append("EMA8 > EMA21 (tendência alta)")
        sinais.append(f"RSI {rsi:.1f} (não sobrecomprado)")
        sinais.append("Preço na banda inferior")

    # Sinal de PUT (baixa)
    elif not tendencia_alta and rsi > 35 and preco_atual >= bb_superior:
        confianca = random.uniform(0.85, 0.95)
        tipo_operacao = "PUT"
        sinais.append("EMA8 < EMA21 (tendência baixa)")
        sinais.append(f"RSI {rsi:.1f} (não sobrevendido)")
        sinais.append("Preço na banda superior")

    # Sem sinal claro
    else:
        return {
            "executada": False,
            "razao": f"Aguardando sinal claro - RSI: {rsi:.1f}, Tendência: {'Alta' if tendencia_alta else 'Baixa'}",
            "confianca": 0.0,
            "lucro_atual": lucro_atual,
            "operacoes_ativas": operacoes_ativas,
        }

    # Verifica confiança mínima
    if confianca < config["entrada"]["min_confianca"]:
        return {
            "executada": False,
            "razao": f"Confiança {confianca:.2f} abaixo do mínimo {config['entrada']['min_confianca']}",
            "confianca": confianca,
            "lucro_atual": lucro_atual,
            "operacoes_ativas": operacoes_ativas,
        }

    # Calcula volume da operação
    volume = calcular_volume_entrada(100.0, modo)  # Simula saldo de $100

    # EXECUTA A OPERAÇÃO
    return {
        "executada": True,
        "tipo": tipo_operacao,
        "ativo": ativo,
        "volume": volume,
        "duracao": 15,  # 15 segundos
        "confianca": confianca,
        "razao": f"TURBO {tipo_operacao} - " + " | ".join(sinais),
        "indicadores": {
            "ema8": ema8,
            "ema21": ema21,
            "rsi": rsi,
            "bb_superior": bb_superior,
            "bb_inferior": bb_inferior,
        },
        "lucro_atual": lucro_atual,
        "operacoes_ativas": operacoes_ativas,
    }
