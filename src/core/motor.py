# motor.py - Atualizado para integração total com painel, meta e catalogador

import time
import json
import websocket
import threading
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Callable, Tuple, Optional
import logging

# Importação com fallback para TTLCache
try:
    from cachetools import TTLCache
except ImportError:
    # Fallback simples se cachetools não estiver disponível
    class TTLCache:
        def __init__(self, maxsize=100, ttl=60):  # ttl ignorado no fallback
            self.data = {}
            self.maxsize = maxsize

        def __setitem__(self, key, value):
            if len(self.data) >= self.maxsize:
                # Remove o primeiro item se atingir o limite
                first_key = next(iter(self.data))
                del self.data[first_key]
            self.data[key] = value

        def __getitem__(self, key):
            return self.data[key]

        def get(self, key, default=None):
            return self.data.get(key, default)

        def __contains__(self, key):
            return key in self.data


try:
    from src.config import config
    from src.config.config import obter_limite_posicoes, normalizar_modo_operacao
except ImportError:
    from config import config
    from config.config import obter_limite_posicoes, normalizar_modo_operacao

try:
    from src.core.catalogador import Catalogador, ATIVOS_TURBO_INTEGRADOS
except ImportError:
    from core.catalogador import Catalogador, ATIVOS_TURBO_INTEGRADOS

try:
    from src.core.inteligencia import (
        analisar_micro_scalping,
        state_machine_micro_scalper,
        obter_state_machine,
        MicroScalperState,
    )
except ImportError:
    from core.inteligencia import (
        analisar_micro_scalping,
        state_machine_micro_scalper,
        obter_state_machine,
        MicroScalperState,
    )

try:
    from src.core.deriv_api import (
        DerivAPIClient,
        DerivAPIError,
        DerivAuthError,
        DerivPermissionError,
        DerivAccountNotFoundError,
        sanitizar_url_ws,
    )
except ImportError:
    from core.deriv_api import (
        DerivAPIClient,
        DerivAPIError,
        DerivAuthError,
        DerivPermissionError,
        DerivAccountNotFoundError,
        sanitizar_url_ws,
    )



class SistemaStops:
    """Sistema avançado de stops (stop loss e take profit)"""

    def __init__(self):
        self.stops_ativos = {}  # {operacao_id: {tipo, valor, ativo}}
        self.configuracoes = {
            "stop_loss_percent": 2.0,  # 2% de perda máxima por operação
            "take_profit_percent": 4.0,  # 4% de ganho alvo por operação
            "stop_loss_global_percent": 10.0,  # 10% de perda máxima do saldo
            "take_profit_global_percent": 20.0,  # 20% de ganho alvo do saldo
            "trailing_stop_enabled": True,  # Stop móvel ativado
            "trailing_stop_distance": 1.0,  # 1% de distância do trailing stop
        }
        self.saldo_inicial = 0.0
        self.melhor_resultado = 0.0  # Para trailing stop

        # Sistema de alertas preventivos
        self.alertas_preventivos = True
        self.percentual_alerta = 80  # Alerta aos 80% do stop
        self.alertas_enviados = set()  # Para evitar spam de alertas

        # Logger específico para stops
        try:
            from utils.logger_unificado import log_stops, log_erro_critico

            self.log_stops = log_stops
            self.log_erro_critico = log_erro_critico
        except ImportError:
            self.log_stops = lambda msg, nivel="warning": print(f"STOPS: {msg}")
            self.log_erro_critico = lambda msg, erro=None: print(f"ERRO: {msg}")

    def configurar_stops_por_modo(self, modo: str):
        """Configura stops baseado no modo de operação"""
        configs_modo = {
            "iniciante": {
                "stop_loss_percent": 1.5,
                "take_profit_percent": 3.0,
                "stop_loss_global_percent": 5.0,
                "take_profit_global_percent": 10.0,
                "trailing_stop_enabled": False,
            },
            "intermediario": {
                "stop_loss_percent": 2.0,
                "take_profit_percent": 4.0,
                "stop_loss_global_percent": 8.0,
                "take_profit_global_percent": 15.0,
                "trailing_stop_enabled": True,
            },
            "conservador": {
                "stop_loss_percent": 2.0,
                "take_profit_percent": 4.0,
                "stop_loss_global_percent": 8.0,
                "take_profit_global_percent": 15.0,
                "trailing_stop_enabled": True,
            },
            "agressivo": {
                "stop_loss_percent": 3.0,
                "take_profit_percent": 6.0,
                "stop_loss_global_percent": 15.0,
                "take_profit_global_percent": 25.0,
                "trailing_stop_enabled": True,
            },
        }

        if modo in configs_modo:
            self.configuracoes.update(configs_modo[modo])

    def adicionar_stop_operacao(
        self, operacao_id: str, valor_entrada: float, tipo_operacao: str, ativo: str
    ):
        """Adiciona stops para uma operação específica"""
        stop_loss_valor = valor_entrada * (
            self.configuracoes["stop_loss_percent"] / 100
        )
        take_profit_valor = valor_entrada * (
            self.configuracoes["take_profit_percent"] / 100
        )

        self.stops_ativos[operacao_id] = {
            "valor_entrada": valor_entrada,
            "stop_loss": stop_loss_valor,
            "take_profit": take_profit_valor,
            "tipo_operacao": tipo_operacao,
            "ativo": ativo,
            "timestamp": datetime.now(),
            "trailing_stop_ativo": self.configuracoes["trailing_stop_enabled"],
            "melhor_resultado_operacao": 0.0,
        }

    def verificar_stops_operacao(
        self, operacao_id: str, resultado_atual: float
    ) -> dict:
        """Verifica se algum stop foi atingido para uma operação com alertas preventivos"""
        try:
            if operacao_id not in self.stops_ativos:
                return {"acao": "continuar", "razao": "Sem stops configurados"}

            stop_info = self.stops_ativos[operacao_id]

            # Verifica alertas preventivos (antes dos stops serem atingidos)
            if self.alertas_preventivos:
                self._verificar_alertas_preventivos(
                    operacao_id, resultado_atual, stop_info
                )

            # Verifica stop loss
            if resultado_atual <= -stop_info["stop_loss"]:
                self.log_stops(
                    f"Stop Loss ATIVADO para {operacao_id}: -{stop_info['stop_loss']:.2f} (Resultado: {resultado_atual:.2f})",
                    "error",
                )
                # Remove da lista de alertas enviados
                self.alertas_enviados.discard(f"{operacao_id}_stop_loss")
                return {
                    "acao": "fechar",
                    "tipo": "stop_loss",
                    "razao": f"Stop Loss atingido: -{stop_info['stop_loss']:.2f}",
                    "resultado": resultado_atual,
                }

            # Verifica take profit
            if resultado_atual >= stop_info["take_profit"]:
                self.log_stops(
                    f"Take Profit ATIVADO para {operacao_id}: +{stop_info['take_profit']:.2f} (Resultado: {resultado_atual:.2f})",
                    "info",
                )
                # Remove da lista de alertas enviados
                self.alertas_enviados.discard(f"{operacao_id}_take_profit")
                return {
                    "acao": "fechar",
                    "tipo": "take_profit",
                    "razao": f"Take Profit atingido: +{stop_info['take_profit']:.2f}",
                    "resultado": resultado_atual,
                }
        except Exception as e:
            self.log_erro_critico(f"Erro na verificação de stops para {operacao_id}", e)
            return {"acao": "continuar", "razao": f"Erro na verificação: {str(e)}"}

        # Verifica trailing stop
        if (
            stop_info["trailing_stop_ativo"]
            and resultado_atual > stop_info["melhor_resultado_operacao"]
        ):
            stop_info["melhor_resultado_operacao"] = resultado_atual
            # Atualiza trailing stop
            trailing_distance = stop_info["valor_entrada"] * (
                self.configuracoes["trailing_stop_distance"] / 100
            )
            novo_stop = resultado_atual - trailing_distance
            if novo_stop > -stop_info["stop_loss"]:
                stop_info["stop_loss"] = -novo_stop

        return {"acao": "continuar", "razao": "Dentro dos limites"}

    def verificar_stops_globais(self, saldo_atual: float) -> dict:
        """Verifica stops globais baseados no saldo total"""
        if self.saldo_inicial == 0 and saldo_atual > 0:
            self.saldo_inicial = saldo_atual

        if self.saldo_inicial <= 0:
            return {"acao": "continuar", "razao": "Aguardando saldo inicial"}

        resultado_total = saldo_atual - self.saldo_inicial
        resultado_percent = (resultado_total / self.saldo_inicial) * 100

        # Stop loss global
        if resultado_percent <= -self.configuracoes["stop_loss_global_percent"]:
            return {
                "acao": "parar_sistema",
                "tipo": "stop_loss_global",
                "razao": f"Stop Loss Global atingido: {resultado_percent:.1f}%",
                "resultado": resultado_total,
            }

        # Take profit global
        if resultado_percent >= self.configuracoes["take_profit_global_percent"]:
            return {
                "acao": "parar_sistema",
                "tipo": "take_profit_global",
                "razao": f"Take Profit Global atingido: {resultado_percent:.1f}%",
                "resultado": resultado_total,
            }

        # Atualiza trailing stop global
        if (
            self.configuracoes["trailing_stop_enabled"]
            and resultado_total > self.melhor_resultado
        ):
            self.melhor_resultado = resultado_total

        return {"acao": "continuar", "razao": "Dentro dos limites globais"}

    def _verificar_alertas_preventivos(
        self, operacao_id: str, resultado_atual: float, stop_info: dict
    ):
        """Verifica e envia alertas preventivos antes dos stops serem atingidos"""
        try:
            # Calcula percentuais de proximidade dos stops
            stop_loss_threshold = -stop_info["stop_loss"] * (
                self.percentual_alerta / 100
            )
            take_profit_threshold = stop_info["take_profit"] * (
                self.percentual_alerta / 100
            )

            # Alerta de proximidade do stop loss
            if (
                resultado_atual <= stop_loss_threshold
                and f"{operacao_id}_stop_loss" not in self.alertas_enviados
            ):

                percentual_atual = abs(resultado_atual / stop_info["stop_loss"]) * 100
                self.log_stops(
                    f"⚠️ ALERTA: Operação {operacao_id} próxima do Stop Loss ({percentual_atual:.1f}% do limite)",
                    "warning",
                )
                self.alertas_enviados.add(f"{operacao_id}_stop_loss")

            # Alerta de proximidade do take profit
            if (
                resultado_atual >= take_profit_threshold
                and f"{operacao_id}_take_profit" not in self.alertas_enviados
            ):

                percentual_atual = (resultado_atual / stop_info["take_profit"]) * 100
                self.log_stops(
                    f"🎯 ALERTA: Operação {operacao_id} próxima do Take Profit ({percentual_atual:.1f}% do objetivo)",
                    "info",
                )
                self.alertas_enviados.add(f"{operacao_id}_take_profit")

        except Exception as e:
            self.log_erro_critico(f"Erro nos alertas preventivos para {operacao_id}", e)

    def remover_stop_operacao(self, operacao_id: str):
        """Remove stops de uma operação finalizada"""
        if operacao_id in self.stops_ativos:
            del self.stops_ativos[operacao_id]

    def obter_status_stops(self) -> dict:
        """Retorna status atual de todos os stops"""
        return {
            "stops_ativos": len(self.stops_ativos),
            "configuracoes": self.configuracoes,
            "melhor_resultado": self.melhor_resultado,
            "saldo_inicial": self.saldo_inicial,
            "operacoes_com_stops": list(self.stops_ativos.keys()),
        }


class GestaoRiscos:
    """Sistema avançado de gestão de riscos integrado com monitoramento em tempo real"""

    def __init__(self):
        self.historico_operacoes = []
        self.sistema_stops = SistemaStops()  # Integra sistema de stops
        self.metricas_tempo_real = {
            "drawdown_atual": 0.0,
            "drawdown_maximo": 0.0,
            "sequencia_perdas": 0,
            "sequencia_ganhos": 0,
            "maior_sequencia_perdas": 0,
            "valor_total_risco": 0.0,
            "operacoes_simultaneas": 0,
            "win_rate_sessao": 0.0,
            "profit_factor": 0.0,
            "risco_por_operacao": 2.0,  # % do saldo
            "risco_maximo_diario": 10.0,  # % do saldo
            "stop_loss_ativo": False,
            "take_profit_ativo": False,
        }
        self.limites_por_modo = {
            "iniciante": {
                "max_operacoes_simultaneas": 3,
                "max_valor_operacao": 20.0,
                "max_risco_diario": 5.0,
                "max_drawdown": 3.0,
                "max_sequencia_perdas": 3,
                "intervalo_min_operacoes": 5.0,
            },
            "intermediario": {
                "max_operacoes_simultaneas": 5,
                "max_valor_operacao": 50.0,
                "max_risco_diario": 8.0,
                "max_drawdown": 5.0,
                "max_sequencia_perdas": 4,
                "intervalo_min_operacoes": 3.0,
            },
            "conservador": {
                "max_operacoes_simultaneas": 5,
                "max_valor_operacao": 50.0,
                "max_risco_diario": 8.0,
                "max_drawdown": 5.0,
                "max_sequencia_perdas": 4,
                "intervalo_min_operacoes": 3.0,
            },
            "agressivo": {
                "max_operacoes_simultaneas": 10,
                "max_valor_operacao": 100.0,
                "max_risco_diario": 15.0,
                "max_drawdown": 10.0,
                "max_sequencia_perdas": 6,
                "intervalo_min_operacoes": 1.0,
            },
        }
        self.alertas_ativos = []
        self.ultima_operacao_timestamp = 0

    def validar_operacao(self, valor: float, modo: str, saldo_atual: float) -> dict:
        """Valida se uma operação pode ser executada baseada nos critérios de risco"""
        try:
            limites = self.limites_por_modo.get(
                modo, self.limites_por_modo["conservador"]
            )

            # 1. Valor máximo por operação
            if valor > limites["max_valor_operacao"]:
                return {
                    "permitido": False,
                    "razao": f"Valor ${valor:.2f} excede limite do modo {modo} (máx: ${limites['max_valor_operacao']:.2f})",
                    "codigo": "VALOR_EXCEDIDO",
                }

            # 2. Operações simultâneas
            if (
                self.metricas_tempo_real["operacoes_simultaneas"]
                >= limites["max_operacoes_simultaneas"]
            ):
                return {
                    "permitido": False,
                    "razao": f"Limite de operações simultâneas atingido ({limites['max_operacoes_simultaneas']})",
                    "codigo": "LIMITE_SIMULTANEAS",
                }

            # 3. Drawdown máximo
            if self.metricas_tempo_real["drawdown_atual"] >= limites["max_drawdown"]:
                return {
                    "permitido": False,
                    "razao": f"Drawdown atual {self.metricas_tempo_real['drawdown_atual']:.1f}% excede limite {limites['max_drawdown']:.1f}%",
                    "codigo": "DRAWDOWN_EXCEDIDO",
                }

            # 4. Sequência de perdas
            if (
                self.metricas_tempo_real["sequencia_perdas"]
                >= limites["max_sequencia_perdas"]
            ):
                return {
                    "permitido": False,
                    "razao": f"Sequência de {self.metricas_tempo_real['sequencia_perdas']} perdas consecutivas atingida",
                    "codigo": "SEQUENCIA_PERDAS",
                }

            # 5. Risco diário
            risco_atual = (
                self.metricas_tempo_real["valor_total_risco"] / saldo_atual
            ) * 100
            if risco_atual >= limites["max_risco_diario"]:
                return {
                    "permitido": False,
                    "razao": f"Risco diário {risco_atual:.1f}% excede limite {limites['max_risco_diario']:.1f}%",
                    "codigo": "RISCO_DIARIO_EXCEDIDO",
                }

            # 6. Intervalo entre operações
            tempo_atual = time.time()
            if (
                tempo_atual - self.ultima_operacao_timestamp
                < limites["intervalo_min_operacoes"]
            ):
                return {
                    "permitido": False,
                    "razao": f"Aguarde {limites['intervalo_min_operacoes']}s entre operações",
                    "codigo": "INTERVALO_MINIMO",
                }

            # Operação aprovada
            return {
                "permitido": True,
                "razao": "Operação aprovada pelos critérios de risco",
                "codigo": "APROVADO",
                "risco_calculado": (valor / saldo_atual) * 100,
                "valor_aprovado": valor,
            }

        except Exception as e:
            return {
                "permitido": False,
                "razao": f"Erro na validação de risco: {str(e)}",
                "codigo": "ERRO_VALIDACAO",
            }

    def registrar_operacao(self, operacao: dict) -> None:
        """Registra uma operação e atualiza métricas de risco"""
        try:
            self.historico_operacoes.append(operacao)
            self.ultima_operacao_timestamp = time.time()

            # Atualiza operações simultâneas
            if operacao.get("status") == "aberta":
                self.metricas_tempo_real["operacoes_simultaneas"] += 1
                self.metricas_tempo_real["valor_total_risco"] += operacao.get(
                    "valor", 0
                )

            elif operacao.get("status") == "fechada":
                self.metricas_tempo_real["operacoes_simultaneas"] = max(
                    0, self.metricas_tempo_real["operacoes_simultaneas"] - 1
                )

                resultado = operacao.get("resultado", 0)
                self.metricas_tempo_real["valor_total_risco"] = max(
                    0,
                    self.metricas_tempo_real["valor_total_risco"]
                    - operacao.get("valor", 0),
                )

                # Atualiza sequências
                if resultado > 0:
                    self.metricas_tempo_real["sequencia_ganhos"] += 1
                    self.metricas_tempo_real["sequencia_perdas"] = 0
                else:
                    self.metricas_tempo_real["sequencia_perdas"] += 1
                    self.metricas_tempo_real["sequencia_ganhos"] = 0

                    # Atualiza maior sequência de perdas
                    if (
                        self.metricas_tempo_real["sequencia_perdas"]
                        > self.metricas_tempo_real["maior_sequencia_perdas"]
                    ):
                        self.metricas_tempo_real["maior_sequencia_perdas"] = (
                            self.metricas_tempo_real["sequencia_perdas"]
                        )

            # Recalcula métricas
            self._recalcular_metricas()

        except Exception as e:
            print(f"Erro ao registrar operação: {e}")

    def _recalcular_metricas(self) -> None:
        """Recalcula todas as métricas de risco"""
        try:
            operacoes_fechadas = [
                op for op in self.historico_operacoes if op.get("status") == "fechada"
            ]

            if not operacoes_fechadas:
                return

            # Win Rate
            wins = len([op for op in operacoes_fechadas if op.get("resultado", 0) > 0])
            total = len(operacoes_fechadas)
            self.metricas_tempo_real["win_rate_sessao"] = (
                (wins / total * 100) if total > 0 else 0
            )

            # Profit Factor
            lucros = sum(
                [
                    op.get("resultado", 0)
                    for op in operacoes_fechadas
                    if op.get("resultado", 0) > 0
                ]
            )
            perdas = abs(
                sum(
                    [
                        op.get("resultado", 0)
                        for op in operacoes_fechadas
                        if op.get("resultado", 0) < 0
                    ]
                )
            )
            self.metricas_tempo_real["profit_factor"] = (
                (lucros / perdas) if perdas > 0 else 0
            )

            # Drawdown
            saldo_inicial = (
                operacoes_fechadas[0].get("saldo_antes", 100)
                if operacoes_fechadas
                else 100
            )
            pico_saldo = saldo_inicial
            drawdown_atual = 0
            drawdown_maximo = 0

            for op in operacoes_fechadas:
                saldo_atual = op.get("saldo_depois", saldo_inicial)
                if saldo_atual > pico_saldo:
                    pico_saldo = saldo_atual

                drawdown_atual = ((pico_saldo - saldo_atual) / pico_saldo) * 100
                if drawdown_atual > drawdown_maximo:
                    drawdown_maximo = drawdown_atual

            self.metricas_tempo_real["drawdown_atual"] = drawdown_atual
            self.metricas_tempo_real["drawdown_maximo"] = drawdown_maximo

        except Exception as e:
            print(f"Erro ao recalcular métricas: {e}")

    def obter_metricas_tempo_real(self) -> dict:
        """Obtém métricas de risco em tempo real"""
        return {
            **self.metricas_tempo_real,
            "total_operacoes": len(self.historico_operacoes),
            "alertas_ativos": len(self.alertas_ativos),
            "timestamp": datetime.now().isoformat(),
        }

    def verificar_alertas(self, modo: str) -> list:
        """Verifica e retorna alertas de risco ativos"""
        alertas = []
        limites = self.limites_por_modo.get(modo, self.limites_por_modo["conservador"])

        # Alerta de drawdown
        if self.metricas_tempo_real["drawdown_atual"] >= limites["max_drawdown"] * 0.8:
            alertas.append(
                {
                    "tipo": "drawdown",
                    "nivel": (
                        "warning"
                        if self.metricas_tempo_real["drawdown_atual"]
                        < limites["max_drawdown"]
                        else "critical"
                    ),
                    "mensagem": f"Drawdown atual: {self.metricas_tempo_real['drawdown_atual']:.1f}%",
                }
            )

        # Alerta de sequência de perdas
        if (
            self.metricas_tempo_real["sequencia_perdas"]
            >= limites["max_sequencia_perdas"] * 0.7
        ):
            alertas.append(
                {
                    "tipo": "sequencia_perdas",
                    "nivel": (
                        "warning"
                        if self.metricas_tempo_real["sequencia_perdas"]
                        < limites["max_sequencia_perdas"]
                        else "critical"
                    ),
                    "mensagem": f"Sequência de {self.metricas_tempo_real['sequencia_perdas']} perdas consecutivas",
                }
            )

        # Alerta de win rate baixo
        if (
            self.metricas_tempo_real["win_rate_sessao"] < 50
            and len(self.historico_operacoes) >= 10
        ):
            alertas.append(
                {
                    "tipo": "win_rate",
                    "nivel": "warning",
                    "mensagem": f"Win rate baixo: {self.metricas_tempo_real['win_rate_sessao']:.1f}%",
                }
            )

        self.alertas_ativos = alertas
        return alertas


class Motor:
    def __init__(self):
        """Inicializa o motor de operações."""
        # Logger específico - DEVE SER PRIMEIRO
        self.logger = logging.getLogger("DerivBot.Motor")

        # Sistema de logs unificado
        try:
            import sys
            import os

            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            from main import LoggerUnificado

            self.logger_unificado = LoggerUnificado
        except ImportError:
            self.logger_unificado = None

        self.ws = None
        self.conectado = False
        self.token = None
        self.saldo = 0.0
        self.id_conta_real = None  # ID real da conta obtido da API
        self.operacoes_abertas = {}
        self.historico_operacoes = []
        self.callback_tick = None
        self.ultima_resposta = None
        self.ultima_cotacao = None
        # Micro-Scalper Inviolável (Issues #2, #3, #4)
        self.ultimo_fechamento_ts = 0.0
        self.req_id_counter = 1
        self.subscricoes_contratos = {}
        self.ultimo_motivo_recusa = "Aguardando ticks para análise"
        self.ultimo_score = 0.0
        self.propostas_recentes = {}
        # SISTEMA DE MÚLTIPLOS ATIVOS PARA SCALPING RÁPIDO (1s prioritários)
        self.ativos_ativos = [
            "1HZ10V",
            "1HZ25V",
            "1HZ50V",
            "1HZ75V",
            "1HZ100V",
            "R_10",
            "R_25",
            "R_50",
        ]  # Múltiplos ativos (1s prioritários)
        self.par_atual = "1HZ75V"  # Ativo principal
        self.ativo_fixo_turbo = False  # Modo multi-ativo habilitado (Issue #5)
        self.rotacao_ativos = True  # Habilita rotação seletiva
        self.ultimo_ativo_usado = 0  # Índice do último ativo usado
        self.tick_subscription_id_por_ativo: Dict[str, str] = {}
        self.ultima_cotacao_por_ativo: Dict[str, float] = {}
        self.ultimo_tick_timestamp_por_ativo: Dict[str, float] = {}
        self.ultima_telemetria_analise: Dict[str, Any] = {}
        self.logger.info(
            f"ESTRATEGIA TURBO MULTI-ATIVO ATIVADA - Ativos: {self.ativos_ativos}"
        )
        self.scanner_ativo = True  # Ativa o scanner de ativos
        self.ultimo_scan_ativo = 0  # Timestamp do último scan
        self.modo_real = getattr(config, "MODO_REAL_PADRAO", True)
        self.catalogador = Catalogador()  # Inicializa catalogador
        # Define o ativo atual no catalogador
        self.catalogador.ativo_atual = self.par_atual

        # Sistema de gestão de riscos integrado
        self.gestao_riscos = GestaoRiscos()

        # Sistema de stops dedicado
        self.sistema_stops = SistemaStops()

        # Log de inicialização
        self.log_unificado("Motor inicializado com sucesso", "success", "sistema")
        self.log_unificado("Sistema de gestão de riscos ativado", "success", "sistema")
        self.log_unificado("Sistema de stops ativado", "success", "sistema")

    def log_unificado(self, mensagem, tipo="info", categoria="motor"):
        """Log usando sistema unificado se disponível"""
        if self.logger_unificado:
            self.logger_unificado.adicionar_log(
                mensagem, tipo, categoria, incluir_painel=True, incluir_tempo_real=True
            )
        else:
            # Fallback para logger padrão
            self.logger.info(f"[{categoria.upper()}] {mensagem}")
        # Define timeframe para micro scalping se disponível
        if hasattr(self.catalogador, "timeframe"):
            self.catalogador.timeframe = 1
        self.rodando = False
        self.meta_atingida = False
        self.saldo_inicial = 0.0
        self.lock = threading.Lock()

        # Sistema inteligente de operações
        self.modo_operacao = "iniciante"
        self.meta_diaria = 20.0
        self.operacoes_ativas_count = 0
        self.protecao_ativa = False

        # Controle de parada de sessão (SESSION STOP - Issue #20)
        self.session_stopped = False
        self.session_stop_reason = None
        self.cooldowns_por_ativo = {}
        self.lucro_acumulado_sessao = 0.0

        # Configura stops baseado no modo inicial
        self.sistema_stops.configurar_stops_por_modo(self.modo_operacao)
        self.sistema_stops.saldo_inicial = self.saldo

        # Carrega configurações de conexão
        conexao_config = getattr(config, "CONEXAO", {})

        # Para tratamento de erros e reconexões
        self.ultima_mensagem_recebida = time.time()
        self.ultimo_tick_timestamp = time.time()
        self.max_inatividade = conexao_config.get(
            "timeout_inatividade", 15
        )  # segundos sem resposta para tentar reconectar
        self.tentativas_reconexao = 0
        self.max_tentativas_reconexao = conexao_config.get(
            "max_tentativas_reconexao", 5
        )
        self.intervalo_tentativas = conexao_config.get(
            "intervalo_tentativas_base", 2
        )  # segundos
        self.intervalo_verificacao = conexao_config.get("intervalo_verificacao", 5)
        self.verificando_conexao = (
            False  # Controle para evitar múltiplas threads de verificação
        )

        # Indica se houve reconexão recente
        self.reconectado_recentemente = False

        # Armazena último erro de autenticação/conexão recebido da Deriv
        self.ultimo_erro = None

        # Iniciar thread de verificação de conexão
        self._iniciar_verificador_conexao()

        # Configurações
        self.config = getattr(config, "BOT_CONFIG", {}).get("MODO_INICIANTE", {})

        # Setup logging
        log_level = getattr(config, "LOG_CONFIG", {}).get("level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler("trading.log"), logging.StreamHandler()],
        )

        self.etapa_atual = ""
        self.progresso = 0
        self.logs = []

        # Sistema de reconexão unificado e otimizado
        self.max_tentativas_reconexao = 5  # Aumentado para mais robustez
        self.tempo_entre_tentativas = 3  # Reduzido para reconexão mais rápida
        self.ultima_tentativa = 0
        self.cache_operacoes = TTLCache(maxsize=100, ttl=60)

    def _proximo_req_id(self) -> int:
        """Gera um request ID único para correlacionar chamadas da API Deriv."""
        self.req_id_counter = getattr(self, "req_id_counter", 1) + 1
        return int(time.time() * 1000) % 100000000 + self.req_id_counter

    def validar_gateway_risco(self, valor_ordem: float = 0.35, ativo: Optional[str] = None) -> Tuple[bool, str]:
        """
        GATEWAY DE RISCO INVIOLÁVEL (Issues #2, #3, #4, #20).
        Bloqueia qualquer execução se:
        - Sessão parada (SESSION STOP: meta atingida, perda realizada, erro ou kill switch)
        - Limite de concorrência por perfil atingido (Iniciante 3, Intermediário 5, Agressivo 10)
        - Ativo especificado em período de cooldown pós-operação (ou cooldown global)
        - Cotação / tick obsoleto (stale > 2.5s)
        - Saldo insuficiente
        - Meta diária atingida
        """
        # 0. Sessão parada
        if getattr(self, "session_stopped", False):
            motivo_stop = getattr(self, "session_stop_reason", "Sessão finalizada")
            return False, f"Gateway Risco: Sessão parada ({motivo_stop})"

        # 1. Posições abertas (Limite seletivo 3 / 5 / 10 por perfil)
        limite_max = obter_limite_posicoes(self.modo_operacao)
        if len(self.operacoes_abertas) >= limite_max:
            return False, f"Gateway Risco: Máximo de {limite_max} operações simultâneas atingido para o perfil '{self.modo_operacao}' ({len(self.operacoes_abertas)}/{limite_max})"

        # 2. Cooldown pós-operação por ativo
        cfg_micro = getattr(config, "MICRO_SCALPER_CONFIG", {})
        cooldown_s = cfg_micro.get("cooldown", {}).get("tempo_minimo_segundos", 25)

        simbolo = (ativo or self.par_atual).upper().strip() if (ativo or self.par_atual) else None
        cooldowns = getattr(self, "cooldowns_por_ativo", {})
        cooldown_ativo_ts = cooldowns.get(simbolo, 0.0) if simbolo else 0.0

        if cooldown_ativo_ts > 0:
            tempo_desde = time.time() - cooldown_ativo_ts
            if tempo_desde < cooldown_s:
                restante = cooldown_s - tempo_desde
                return False, f"Gateway Risco: Ativo {simbolo} em cooldown pós-operação ({restante:.1f}s restantes)"
        elif getattr(self, "ultimo_fechamento_ts", 0.0) > 0 and not ativo:
            # Fallback para checagem global quando nenhum ativo específico foi fornecido
            tempo_desde_fechamento = time.time() - self.ultimo_fechamento_ts
            if tempo_desde_fechamento < cooldown_s:
                restante = cooldown_s - tempo_desde_fechamento
                return False, f"Gateway Risco: Em cooldown pós-operação ({restante:.1f}s restantes)"

        # 3. Frescor dos ticks (stale data) isolado por ativo
        max_stale = cfg_micro.get("gateway_risco", {}).get("tempo_max_tick_stale_s", 2.5)
        simbolo = (ativo or self.par_atual).upper().strip() if (ativo or self.par_atual) else None

        ts_tick = 0.0
        if hasattr(self, "ultimo_tick_timestamp_por_ativo") and self.ultimo_tick_timestamp_por_ativo:
            if simbolo and simbolo in self.ultimo_tick_timestamp_por_ativo:
                ts_tick = self.ultimo_tick_timestamp_por_ativo[simbolo]
            elif not simbolo or simbolo == getattr(self, "par_atual", "1HZ75V"):
                ts_tick = getattr(self, "ultimo_tick_timestamp", 0.0)
        else:
            ts_tick = getattr(self, "ultimo_tick_timestamp", 0.0)

        if ts_tick > 0.0:
            idade_tick = time.time() - ts_tick
            if idade_tick > max_stale:
                return False, f"Gateway Risco: Dados de ticks obsoletos para {simbolo or 'ativo'} ({idade_tick:.1f}s > {max_stale}s)"
        else:
            return False, f"Gateway Risco: Dados de ticks obsoletos ou ausentes para {simbolo or 'ativo'}"

        # 4. Saldo
        min_balance = cfg_micro.get("gateway_risco", {}).get("min_balance_usd", 1.0)
        if self.saldo < (valor_ordem + min_balance):
            return False, f"Gateway Risco: Saldo insuficiente (${self.saldo:.2f} < ${valor_ordem + min_balance:.2f})"

        # 5. Meta diária
        lucro_atual = self.obter_saldo() - self.saldo_inicial
        if self.meta_diaria > 0 and (lucro_atual >= self.meta_diaria or getattr(self, "lucro_acumulado_sessao", 0.0) >= self.meta_diaria):
            return False, f"Gateway Risco: Meta diária de ${self.meta_diaria:.2f} já atingida"

        return True, "Aprovado pelo Gateway de Risco"

    def conectar(
        self,
        token: Optional[str] = None,
        account_id: Optional[str] = None,
        account_type: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> bool:
        """
        Conecta com a API da Deriv usando o novo fluxo oficial (Single PAT + OTP WebSocket).
        Substitui o fluxo legado de 2 tokens independentes.
        """
        pat = token or self.token
        if not pat:
            from config.config import Config
            pat = Config.obter_deriv_pat()

        if not pat or not str(pat).strip():
            self.ultimo_erro = "Token PAT da Deriv não configurado"
            self.logger.error("Token PAT da Deriv não configurado")
            return False

        return self._conectar_com_pat(
            pat=str(pat).strip(),
            account_id=account_id,
            account_type=account_type,
            app_id=app_id,
        )

    def _conectar_com_pat(
        self,
        pat: str,
        account_id: Optional[str] = None,
        account_type: Optional[str] = None,
        app_id: Optional[str] = None,
    ) -> bool:
        """Conecta com a nova API da Deriv usando Personal Access Token (PAT) e OTP."""
        try:
            self.token = pat

            # 1. Resolve app_id
            resolved_app_id = (
                app_id
                or getattr(self, "app_id", None)
                or getattr(config, "DERIV_APP_ID", None)
            )
            if not resolved_app_id:
                from config.config import Config
                resolved_app_id = Config.obter_deriv_app_id()

            if not resolved_app_id or not str(resolved_app_id).strip():
                self.ultimo_erro = "DERIV_APP_ID não configurado"
                self.logger.error("DERIV_APP_ID não configurado")
                return False

            self.app_id = str(resolved_app_id).strip()
            base_url = getattr(config, "DERIV_API_BASE", "https://api.derivws.com")
            client = DerivAPIClient(base_url=base_url)

            # 2. Descobre contas vinculadas se account_id não foi pré-definido
            contas = []
            try:
                contas = client.listar_contas(self.token, self.app_id)
                self.contas_disponiveis = contas
            except Exception as ex_list:
                self.logger.error(f"Erro ao listar contas Deriv: {ex_list}")
                self.ultimo_erro = str(ex_list)
                return False

            if not contas:
                self.ultimo_erro = "Nenhuma conta vinculada ao token PAT"
                self.logger.error(self.ultimo_erro)
                return False

            # Determina o tipo de conta desejado (DEMO por padrão; REAL exige solicitação explícita)
            tipo_desejado = account_type or getattr(self, "tipo_conta", "demo")
            modo_real = getattr(config, "MODO_REAL_PADRAO", False)
            preferir_real = (tipo_desejado == "real" or modo_real)

            try:
                conta_alvo = client.selecionar_conta_padrao(
                    contas,
                    preferir_real=preferir_real,
                    account_id_especifico=account_id,
                )
            except DerivAccountNotFoundError as ex_acc:
                self.logger.error(f"Seleção de conta falhou: {ex_acc}")
                self.ultimo_erro = str(ex_acc)
                return False

            account_id = conta_alvo["account_id"]
            tipo_desejado = conta_alvo["account_type"]
            self.saldo = float(conta_alvo.get("balance", 0.0))
            self.saldo_inicial = self.saldo

            self.account_id = account_id
            self.id_conta_real = account_id
            self.account_type = tipo_desejado
            self.tipo_conta = tipo_desejado

            self.logger.info(
                f"[PAT] Conta selecionada: {account_id} ({tipo_desejado}) - Saldo: ${self.saldo:.2f}"
            )

            # 3. Solicita OTP de uso único para a conta selecionada
            try:
                ws_url = self._obter_nova_url_ws_autenticada(account_id=account_id)
            except Exception as ex_otp:
                self.logger.error(f"Falha ao obter OTP da Deriv: {ex_otp}")
                self.ultimo_erro = str(ex_otp)
                return False

            if not ws_url:
                self.ultimo_erro = "Falha ao obter URL com OTP da Deriv"
                return False

            # 4. Conecta diretamente na URL WebSocket retornada com OTP
            self.desconectar()
            self.logger.info(
                f"[PAT] Conectando ao WebSocket autenticado para conta {account_id} ({tipo_desejado})..."
            )

            def _on_open_pat(ws):
                self.logger.info("WebSocket PAT conectado com sucesso!")
                self.conectado = True
                try:
                    # Assina saldo e ticks imediatamente (sem enviar authorize)
                    self.ws.send(json.dumps({"balance": 1, "subscribe": 1}))
                    self._inscrever_ticks()
                except Exception as ex:
                    self.logger.error(f"Erro ao inicializar subscrições WebSocket PAT: {ex}")

            self.ws = websocket.WebSocketApp(
                ws_url,
                on_open=_on_open_pat,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )

            self.tentativas_reconexao = 0
            self.reconectado_recentemente = False

            wst = threading.Thread(target=self.ws.run_forever)
            wst.daemon = True
            wst.start()

            for _ in range(20):
                if self.conectado:
                    self.logger.info(
                        f"Conexão PAT estabelecida com sucesso. Conta: {self.account_id} | Saldo: ${self.saldo:.2f}"
                    )
                    return True
                time.sleep(0.5)

            self.logger.error("Timeout ao conectar via WebSocket PAT.")
            self.ultimo_erro = "Timeout ao conectar via WebSocket PAT"
            return False

        except Exception as e:
            self.logger.error(f"Erro ao conectar via PAT: {e}", exc_info=True)
            self.ultimo_erro = f"Erro na autenticação PAT: {e}"
            return False

    def _obter_nova_url_ws_autenticada(self, account_id: Optional[str] = None) -> str:
        """Obtém uma nova URL autenticada com OTP de uso único para conexão ou reconexão."""
        acc_id = account_id or getattr(self, "account_id", None)
        base_url = getattr(config, "DERIV_API_BASE", "https://api.derivws.com")
        client = DerivAPIClient(base_url=base_url)
        return client.solicitar_otp(self.token, self.app_id, acc_id)

    def _on_message(self, _, message):
        """Callback para processar mensagens recebidas do WebSocket."""
        try:
            # Atualiza o timestamp da última mensagem recebida
            self.ultima_mensagem_recebida = time.time()

            # Reduz verbosidade para mensagens frequentes (ticks).
            # IMPORTANTE: este bloco controla apenas log. O frescor do tick é
            # atualizado quando uma mensagem de tick válida é realmente processada.
            if '"tick"' not in message or time.time() - self.ultimo_tick_timestamp > 5:
                self.logger.debug(f"Mensagem recebida: {message[:100]}...")

            data = json.loads(message)
            self.ultima_resposta = data

            # Processamento da autorização
            if "authorize" in data and data["authorize"]:
                self.conectado = True
                self.saldo = data["authorize"].get("balance", 0)
                self.saldo_inicial = self.saldo

                # Captura o ID real da conta
                auth_data = data["authorize"]
                if "loginid" in auth_data:
                    self.id_conta_real = auth_data["loginid"]
                    self.logger.info(
                        f"✅ ID real da conta capturado: {self.id_conta_real}"
                    )
                else:
                    self.logger.warning(
                        "⚠️ ID da conta não encontrado na resposta de autorização"
                    )

                self.logger.info(f"Autenticado com sucesso. Saldo: {self.saldo}")

                # Agora inscreve nos ticks
                self._inscrever_ticks()

                # Reseta contadores de reconexão
                self.tentativas_reconexao = 0
                if self.reconectado_recentemente:
                    self.logger.info("Reconexão bem-sucedida!")
                    self.reconectado_recentemente = False

            # Processamento de atualizações de saldo (streaming/subscrição)
            if "balance" in data and data["balance"]:
                bal_data = data["balance"]
                if isinstance(bal_data, dict):
                    self.saldo = float(bal_data.get("balance", self.saldo))
                    if not self.saldo_inicial or self.saldo_inicial <= 0:
                        self.saldo_inicial = self.saldo
                    login_id = bal_data.get("loginid")
                    if login_id:
                        self.id_conta_real = login_id
                elif isinstance(bal_data, (int, float)):
                    self.saldo = float(bal_data)
                    if not self.saldo_inicial or self.saldo_inicial <= 0:
                        self.saldo_inicial = self.saldo

            # Processamento de ticks isolado por ativo
            if "tick" in data and data["tick"]:
                tick_data = data["tick"]
                now_ts = time.time()
                symbol = str(
                    tick_data.get("symbol")
                    or data.get("echo_req", {}).get("ticks")
                    or self.par_atual
                ).upper().strip()
                quote = float(tick_data.get("quote", 0.0))

                sub_id = data.get("subscription", {}).get("id") or tick_data.get("id")
                if sub_id and symbol:
                    self.tick_subscription_id_por_ativo[symbol] = str(sub_id)

                self.ultimo_tick_timestamp_por_ativo[symbol] = now_ts
                self.ultima_cotacao_por_ativo[symbol] = quote

                # Roteia para catalogador com símbolo explícito (sem contaminação)
                self.catalogador.adicionar_tick(quote, timestamp=now_ts, ativo=symbol)

                # Mantém sincronizado com par_atual se for o caso
                if symbol == self.par_atual:
                    self.ultimo_tick_timestamp = now_ts
                    self.ultima_cotacao = quote
                    if self.callback_tick:
                        self.callback_tick(self.ultima_cotacao)
                elif not hasattr(self, "ultima_cotacao") or self.ultima_cotacao is None or self.ultima_cotacao == 0:
                    self.ultimo_tick_timestamp = now_ts
                    self.ultima_cotacao = quote

                # Não executamos operações diretamente aqui, apenas através do app.py
                # que controlará corretamente os valores de entrada

                # Verifica operações que precisam ser fechadas automaticamente (micro scalping)
                self._verificar_fechamento_automatico()

            # Processamento de abertura de contratos
            if "buy" in data and data["buy"]:
                contract_id = data["buy"]["contract_id"]

                transaction_id = None
                if "passthrough" in data and data["passthrough"]:
                    transaction_id = data["passthrough"].get("transaction_id")

                symbol = data.get("echo_req", {}).get("parameters", {}).get("symbol", self.par_atual)
                with self.lock:
                    self.operacoes_abertas[contract_id] = {
                        "id": contract_id,
                        "ativo": symbol,
                        "preco_entrada": data["buy"]["buy_price"],
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "tipo": data.get("echo_req", {})
                        .get("parameters", {})
                        .get("contract_type", ""),
                        "transaction_id": transaction_id,
                        "timestamp_abertura": time.time(),
                        "positive_updates": 0,
                        "motivo_saida": "",
                        "fechamento_automatico": False,
                    }

                    if transaction_id and hasattr(self, "transacoes_pendentes"):
                        if transaction_id in self.transacoes_pendentes:
                            self.transacoes_pendentes[transaction_id]["processada"] = True
                            self.transacoes_pendentes[transaction_id]["contract_id"] = contract_id

                self.logger.info(
                    f"✅ Operação {contract_id} ({symbol}) confirmada na Deriv. Subscrevendo proposal_open_contract..."
                )

                # Subscreve para atualizações contínuas em tempo real
                sub_req = {
                    "proposal_open_contract": 1,
                    "contract_id": contract_id,
                    "subscribe": 1,
                    "req_id": self._proximo_req_id(),
                }
                self.ws.send(json.dumps(sub_req))
                
                # Atualiza state machine específica do ativo e global
                sm_ativo = obter_state_machine(symbol)
                sm_ativo.transitar(
                    MicroScalperState.POSICAO_ABERTA,
                    f"Contrato {contract_id} ({symbol}) aberto na Deriv",
                )
                state_machine_micro_scalper.transitar(
                    MicroScalperState.POSICAO_ABERTA,
                    f"Contrato {contract_id} ({symbol}) aberto na Deriv",
                )

                # Adiciona stops para a operação
                valor_entrada = data["buy"]["buy_price"]
                tipo_operacao = (
                    data.get("echo_req", {})
                    .get("parameters", {})
                    .get("contract_type", "")
                )
                self.sistema_stops.adicionar_stop_operacao(
                    contract_id, valor_entrada, tipo_operacao, symbol
                )

            # Processamento de atualização/fechamento de contratos
            if "proposal_open_contract" in data and data["proposal_open_contract"]:
                contract = data["proposal_open_contract"]
                contract_id = contract["contract_id"]

                # Armazena subscription_id se presente
                if "subscription" in data and "id" in data["subscription"]:
                    self.subscricoes_contratos[contract_id] = data["subscription"]["id"]

                if contract_id in self.operacoes_abertas:
                    operacao = self.operacoes_abertas[contract_id]
                    is_sold = contract.get("is_sold", 0)
                    is_valid_to_sell = contract.get("is_valid_to_sell", 0)
                    profit = float(contract.get("profit", 0.0))
                    tempo_aberto = time.time() - operacao.get("timestamp_abertura", time.time())

                    # Se a operação ainda está aberta:
                    if is_sold == 0:
                        cfg_saida = getattr(config, "MICRO_SCALPER_CONFIG", {}).get("saida", {})
                        min_exit_profit = cfg_saida.get("min_exit_profit", 0.02)
                        min_pos_updates = cfg_saida.get("min_positive_updates", 2)
                        max_hold_s = cfg_saida.get("max_hold_seconds", 45)

                        # Contagem de updates positivos
                        if profit >= min_exit_profit:
                            operacao["positive_updates"] = operacao.get("positive_updates", 0) + 1
                        else:
                            operacao["positive_updates"] = 0

                        # REGRA 1: SAÍDA NO PRIMEIRO LUCRO LÍQUIDO CONFIRMADO
                        if operacao.get("positive_updates", 0) >= min_pos_updates and is_valid_to_sell == 1:
                            self.logger.info(
                                f"🎯 PRIMEIRO LUCRO LÍQUIDO CONFIRMADO! Venda antecipada disparada para {contract_id} "
                                f"com lucro de +${profit:.4f} (após {tempo_aberto:.1f}s)"
                            )
                            state_machine_micro_scalper.transitar(
                                MicroScalperState.SAINDO,
                                f"Primeiro lucro atingido: +${profit:.4f}",
                            )
                            operacao["motivo_saida"] = "FIRST_POSITIVE_PROFIT"
                            self.fechar_operacao(contract_id)

                        # REGRA 2: TIMEOUT MÁXIMO DE SEGURANÇA
                        elif tempo_aberto >= max_hold_s and is_valid_to_sell == 1:
                            self.logger.info(
                                f"⏱️ Timeout de retenção ({tempo_aberto:.1f}s >= {max_hold_s}s) para {contract_id}. "
                                f"Encerrando operação (Profit: ${profit:.4f})..."
                            )
                            state_machine_micro_scalper.transitar(
                                MicroScalperState.SAINDO,
                                f"Timeout retenção atingido ({max_hold_s}s)",
                            )
                            operacao["motivo_saida"] = "MAX_HOLD_TIMEOUT"
                            self.fechar_operacao(contract_id)

                        # REGRA 3: STOPS TRADICIONAIS
                        else:
                            verificacao_stop = self.sistema_stops.verificar_stops_operacao(
                                contract_id, profit
                            )
                            if verificacao_stop.get("acao") == "fechar" and is_valid_to_sell == 1:
                                self.logger.info(
                                    f"🛑 {verificacao_stop['razao']} - Fechando operação {contract_id}"
                                )
                                state_machine_micro_scalper.transitar(
                                    MicroScalperState.SAINDO,
                                    verificacao_stop.get("razao", "Stop"),
                                )
                                operacao["motivo_saida"] = "STOP_DISPARADO"
                                self._fechar_operacao_por_stop(contract_id, verificacao_stop)

                    # Se a operação foi finalizada (is_sold == 1):
                    elif is_sold == 1:
                        lucro = float(contract.get("profit", 0.0))
                        motivo_saida = operacao.get("motivo_saida", "CONTRATO_EXPIRADO")
                        ativo_op = operacao.get("ativo", self.par_atual)

                        self.logger.info(
                            f"🏁 Operação {contract_id} ({ativo_op}) finalizada com lucro: ${lucro:+.4f} | Motivo: {motivo_saida}"
                        )

                        # Envia forget para encerrar a stream do contrato
                        sub_id = self.subscricoes_contratos.pop(contract_id, None)
                        if sub_id:
                            try:
                                self.ws.send(json.dumps({"forget": sub_id}))
                            except Exception as e:
                                self.logger.debug(f"Erro ao enviar forget para {sub_id}: {e}")

                        # Registra na máquina de estados do ativo e global, e ativa cooldown do ativo
                        if not hasattr(self, "cooldowns_por_ativo"):
                            self.cooldowns_por_ativo = {}
                        self.cooldowns_por_ativo[ativo_op] = time.time()
                        self.ultimo_fechamento_ts = time.time()

                        sm_ativo = obter_state_machine(ativo_op)
                        sm_ativo.registrar_resultado_operacao(lucro, motivo_saida)
                        sm_ativo.transitar(
                            MicroScalperState.COOLDOWN,
                            f"Pós-operação {ativo_op} (Resultado: ${lucro:+.2f})",
                        )
                        state_machine_micro_scalper.registrar_resultado_operacao(lucro, motivo_saida)
                        state_machine_micro_scalper.transitar(
                            MicroScalperState.COOLDOWN,
                            f"Pós-operação (Resultado: ${lucro:+.2f})",
                        )

                        with self.lock:
                            preco_entrada = operacao.get("preco_entrada", 0.0)
                            resultado = {
                                "id": contract_id,
                                "ativo": ativo_op,
                                "preco_entrada": preco_entrada,
                                "preco_saida": contract.get("sell_price", 0.0),
                                "lucro": lucro,
                                "motivo_saida": motivo_saida,
                                "timestamp_abertura": operacao.get("timestamp"),
                                "timestamp_fechamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "tipo": operacao.get("tipo"),
                            }
                            self.historico_operacoes.append(resultado)
                            if "balance_after" in contract:
                                self.saldo = float(contract["balance_after"])

                            try:
                                import main
                                main.adicionar_operacao(
                                    tipo=operacao.get("tipo", "UNKNOWN"),
                                    valor=operacao.get("valor", 0),
                                    resultado=lucro,
                                )
                            except Exception as e:
                                self.logger.debug(f"Erro ao notificar operação no main: {e}")

                            del self.operacoes_abertas[contract_id]
                            self.sistema_stops.remover_stop_operacao(contract_id)

                        resultado_texto = "GANHO" if lucro >= 0 else "PERDA"
                        self.logger.info(
                            f"Operação {contract_id} ({ativo_op}) fechada com {resultado_texto}: ${lucro:.2f} (Saldo atual: ${self.saldo:.2f})"
                        )

                        # ==============================================================
                        # SESSION STOP: PARADA DE SESSÃO IMEDIATA (Issue #20)
                        # - PRIMEIRA PERDA REALIZADA (lucro <= 0)
                        # - META ATINGIDA (lucro_total >= meta)
                        # ==============================================================
                        if lucro <= 0:
                            self.session_stopped = True
                            self.session_stop_reason = (
                                f"PRIMEIRA_PERDA_REALIZADA: Operação {contract_id} ({ativo_op}) fechou com perda (${lucro:+.4f})"
                            )
                            self.logger.warning(
                                f"🛑 [SESSION STOP] {self.session_stop_reason}. Novas entradas bloqueadas! "
                                f"Contratos abertos restantes ({len(self.operacoes_abertas)}) continuarão sendo monitorados até liquidação."
                            )
                        else:
                            self.lucro_acumulado_sessao = getattr(self, "lucro_acumulado_sessao", 0.0) + lucro
                            lucro_total = self.obter_saldo() - self.saldo_inicial
                            take_profit = getattr(config, "TAKE_PROFIT", self.meta_diaria)
                            if self.meta_diaria > 0 and (lucro_total >= take_profit or self.lucro_acumulado_sessao >= self.meta_diaria):
                                self.session_stopped = True
                                self.session_stop_reason = (
                                    f"META_ATINGIDA: Lucro acumulado ${lucro_total:+.2f} atingiu a meta de ${self.meta_diaria:.2f}"
                                )
                                self.meta_atingida = True
                                self.logger.info(
                                    f"🎯 [SESSION STOP] {self.session_stop_reason}. Novas entradas bloqueadas! "
                                    f"Contratos abertos restantes ({len(self.operacoes_abertas)}) continuarão sendo monitorados até liquidação."
                                )

            # Captura erros retornados pela API
            if "error" in data:
                self.ultimo_erro = data["error"].get("message", "Erro desconhecido")
                self.logger.error(f"[DERIV ERROR] {self.ultimo_erro}")

                # Trata possíveis erros de autorização
                if (
                    "AuthorizationRequired" in self.ultimo_erro
                    or "token" in self.ultimo_erro.lower()
                    or "invalid" in self.ultimo_erro.lower()
                ):
                    self.conectado = False
                    self.logger.error(
                        f"[AUTH ERROR] Token inválido ou não autorizado: {self.ultimo_erro}. Reconexão automática desativada."
                    )
                else:
                    self._agendar_reconexao()

        except json.JSONDecodeError as e:
            self.logger.error(f"Erro ao decodificar JSON: {str(e)}")
        except Exception as e:
            self.logger.error(f"Erro ao processar mensagem: {str(e)}", exc_info=True)

    def _on_error(self, _, error):
        """Callback para tratar erros do WebSocket."""
        # SILENCIA ERROS COMUNS PARA EVITAR SPAM
        error_str = str(error).lower()
        if any(
            x in error_str
            for x in [
                "rate limit",
                "503",
                "temporarily unavailable",
                "connection closed",
            ]
        ):
            pass  # Não loga erros temporários
        else:
            self.logger.warning(f"Conexão perdida: {str(error)}")

        self.ultimo_erro = f"Erro de conexão: {str(error)}"
        self.conectado = False

    def _on_close(self, _, close_status_code, close_msg):
        """Callback para quando a conexão é fechada."""
        self.conectado = False
        self.tick_subscription_id_por_ativo.clear()
        self.logger.warning(
            f"Conexão fechada. Código: {close_status_code}, Msg: {close_msg}"
        )

        # Agenda reconexão se não for fechamento intencional
        if close_status_code != 1000:  # 1000 é fechamento normal
            self._agendar_reconexao()

    def _inscrever_ticks(self):
        """Inscreve para receber ticks de todos os ativos monitorados com deduplicação."""
        try:
            if not self.ws or not self.conectado:
                self.logger.warning("Não é possível inscrever ticks: não conectado")
                return False

            pool_ativos = list(self.ativos_ativos)
            if self.par_atual not in pool_ativos:
                pool_ativos.append(self.par_atual)

            inscricoes_feitas = 0
            for ativo in pool_ativos:
                if ativo in self.tick_subscription_id_por_ativo and self.tick_subscription_id_por_ativo[ativo]:
                    continue  # Deduplicação: já inscrito

                req = {"ticks": ativo, "subscribe": 1, "req_id": self._proximo_req_id()}
                self.ws.send(json.dumps(req))
                self.logger.info(f"Inscrito para receber ticks de {ativo}")
                inscricoes_feitas += 1

            # Atualiza o ativo do scanner se oportuno
            self._atualizar_ativo_scanner()
            return True
        except Exception as e:
            self.logger.error(f"Erro ao inscrever ticks: {str(e)}")
            return False

    def _atualizar_ativo_scanner(self):
        """Atualiza o ativo usando dados reais do scanner se disponíveis"""
        try:
            import time

            agora = time.time()
            if agora - self.ultimo_scan_ativo < 60:
                return

            self.ultimo_scan_ativo = agora

            if not self.scanner_ativo:
                return

            # Inicializa o scanner se necessário
            if not hasattr(self.catalogador, "ativos_priorizados"):
                self.catalogador.inicializar_scanner_ativos()

            # Obtém o melhor ativo por análise técnica real
            melhor_ativo = self.catalogador.analisar_melhor_ativo()

            # Muda o ativo se houver melhor oportunidade comprovada
            if melhor_ativo and melhor_ativo != self.par_atual:
                self.logger.info(f"Scanner multi-ativo: selecionado {melhor_ativo} (melhor assertividade)")
                self.definir_par(melhor_ativo)

        except Exception as e:
            self.logger.error(f"Erro no scanner de ativos: {e}")

    # FUNÇÃO REMOVIDA - Usar catalogador.obter_ativo_recomendado() diretamente

    def _analisar_entrada_turbo(
        self, ativo, preco_atual, modo, meta, lucro_atual, operacoes_ativas
    ):
        """
        ANÁLISE CANÔNICA DO MICRO-SCALPER SELETIVO (Issues #2, #3, #4, #20).
        Zero random: 100% determinístico baseado em extremos estatísticos,
        confirmação de reversão e score de confluência >= 85.
        Suporta multi-ativos e concorrência 3 / 5 / 10 posições por perfil.
        """
        ativo_alvo = ativo or self.par_atual

        # 0. Checagem de parada de sessão (SESSION STOP)
        if getattr(self, "session_stopped", False):
            motivo = f"Sessão parada ({getattr(self, 'session_stop_reason', 'SESSION_STOP')})"
            self.ultimo_motivo_recusa = motivo
            return {
                "executada": False,
                "sinal": False,
                "tipo": None,
                "ativo": ativo_alvo,
                "razao": motivo,
                "motivo_recusa": motivo,
                "confianca": 0.0,
                "score": 0.0,
                "estado": MicroScalperState.NORMAL,
                "lucro_atual": lucro_atual,
                "operacoes_ativas": operacoes_ativas,
            }

        # 1. Checagem prévia de operações ativas (Limite dinâmico 3/5/10 por perfil)
        limite_pos = obter_limite_posicoes(modo)
        if operacoes_ativas >= limite_pos:
            motivo = f"Máximo de {limite_pos} operações simultâneas atingido para o perfil '{modo}' ({operacoes_ativas}/{limite_pos})"
            self.ultimo_motivo_recusa = motivo
            return {
                "executada": False,
                "sinal": False,
                "tipo": None,
                "ativo": ativo_alvo,
                "razao": motivo,
                "motivo_recusa": motivo,
                "confianca": 0.0,
                "score": 0.0,
                "estado": MicroScalperState.POSICAO_ABERTA,
                "lucro_atual": lucro_atual,
                "operacoes_ativas": operacoes_ativas,
            }

        # 2. Checagem de meta diária
        if meta > 0 and lucro_atual >= meta:
            motivo = f"Meta diária de ${meta:.2f} já atingida (Lucro atual: ${lucro_atual:.2f})"
            self.ultimo_motivo_recusa = motivo
            return {
                "executada": False,
                "sinal": False,
                "tipo": None,
                "ativo": ativo_alvo,
                "razao": motivo,
                "motivo_recusa": motivo,
                "confianca": 0.0,
                "score": 0.0,
                "estado": MicroScalperState.NORMAL,
                "lucro_atual": lucro_atual,
                "operacoes_ativas": operacoes_ativas,
            }

        # 3. Snapshot de mercado e ticks reais para o ativo alvo
        snapshot = {}
        ultimos_ticks = []
        if hasattr(self.catalogador, "obter_snapshot_mercado"):
            snapshot = self.catalogador.obter_snapshot_mercado(ativo_alvo)
        if hasattr(self.catalogador, "obter_ultimos_ticks"):
            try:
                ultimos_ticks = self.catalogador.obter_ultimos_ticks(60, ativo=ativo_alvo)
            except TypeError:
                ultimos_ticks = self.catalogador.obter_ultimos_ticks(60)

        # Se dados insuficientes, aguarda sem forçar
        if not snapshot.get("valido", False) or len(ultimos_ticks) < 15:
            motivo = f"Aguardando ticks para análise estatística de {ativo_alvo} ({len(ultimos_ticks)}/15 ticks recebidos)"
            self.ultimo_motivo_recusa = motivo
            return {
                "executada": False,
                "sinal": False,
                "tipo": None,
                "ativo": ativo_alvo,
                "razao": motivo,
                "motivo_recusa": motivo,
                "confianca": 0.0,
                "score": 0.0,
                "estado": MicroScalperState.NORMAL,
                "lucro_atual": lucro_atual,
                "operacoes_ativas": operacoes_ativas,
            }

        # 4. Avaliação seletiva de micro-scalping determinística
        resultado_intel = analisar_micro_scalping(
            dados_ou_snapshot=snapshot,
            meta=meta,
            lucro_atual=lucro_atual,
            modo=modo,
            operacoes_ativas=operacoes_ativas,
            ultimos_ticks=ultimos_ticks,
            ativo=ativo_alvo,
        )

        sinal_direcao = resultado_intel.get("sinal")
        score = resultado_intel.get("score", 0.0)
        confianca = resultado_intel.get("confianca", 0.0)
        razao = resultado_intel.get("razao", "Aguardando confluência")
        motivo_recusa = resultado_intel.get("motivo_recusa", razao)
        estado = resultado_intel.get("estado", MicroScalperState.NORMAL)

        self.ultimo_score = score
        self.ultimo_motivo_recusa = motivo_recusa

        # Volume de entrada escalonado por perfil
        volume = 0.35
        if modo in ["conservador", "intermediario"]:
            volume = 0.50
        elif modo == "agressivo":
            volume = 1.00

        indicadores_resumo = {
            "rsi": snapshot.get("rsi", 50.0),
            "z_score": snapshot.get("z_score", 0.0),
            "percentil_curto": snapshot.get("percentil_curto", 50.0),
            "inclinacao": snapshot.get("inclinacao_curta", 0.0),
            "bb_dist_inf": snapshot.get("distancia_bb_inferior", 0.0),
            "bb_dist_sup": snapshot.get("distancia_bb_superior", 0.0),
        }

        min_score = resultado_intel.get("min_score", 85.0)

        if not sinal_direcao:
            return {
                "executada": False,
                "sinal": False,
                "tipo": None,
                "ativo": ativo_alvo,
                "razao": razao,
                "motivo_recusa": motivo_recusa,
                "confianca": confianca,
                "score": score,
                "min_score": min_score,
                "estado": estado,
                "indicadores": indicadores_resumo,
                "lucro_atual": lucro_atual,
                "operacoes_ativas": operacoes_ativas,
            }

        return {
            "executada": True,
            "sinal": True,
            "tipo": sinal_direcao,
            "ativo": ativo_alvo,
            "volume": volume,
            "duracao": 15,
            "confianca": confianca,
            "score": score,
            "min_score": min_score,
            "estado": estado,
            "razao": razao,
            "motivo_recusa": "",
            "indicadores": indicadores_resumo,
            "lucro_atual": lucro_atual,
            "operacoes_ativas": operacoes_ativas,
        }

    def registrar_callback_tick(self, callback: Callable[[float], None]):
        """Registra um callback para ser chamado a cada tick recebido."""
        self.callback_tick = callback

    def executar_operacao_inteligente(self, _: str = "default") -> dict:
        """
        Executa análise seletiva determinística através do pool de multi-ativos turbo integrados
        e gerencia entrada através do gateway de risco inviolável.
        """
        try:
            lucro_atual = self.obter_saldo() - self.saldo_inicial
            self.operacoes_ativas_count = len(self.operacoes_abertas)

            # 0. Verificação imediata de SESSION STOP
            if getattr(self, "session_stopped", False):
                motivo = f"Sessão parada ({getattr(self, 'session_stop_reason', 'SESSION_STOP')})"
                return {
                    "executada": False,
                    "razao": motivo,
                    "motivo_recusa": motivo,
                    "confianca": 0.0,
                    "score": 0.0,
                    "estado": MicroScalperState.NORMAL,
                    "lucro_atual": lucro_atual,
                    "operacoes_ativas": self.operacoes_ativas_count,
                    "session_stopped": True,
                }

            # 1. Scanner multi-ativo sobre ATIVOS_TURBO_INTEGRADOS
            ativos_candidatos = list(ATIVOS_TURBO_INTEGRADOS.keys())
            if self.par_atual in ativos_candidatos:
                ativos_candidatos.remove(self.par_atual)
                ativos_candidatos.insert(0, self.par_atual)

            analise = None
            melhor_analise_sem_sinal = None

            for cand_ativo in ativos_candidatos:
                # Se ativo específico estiver em cooldown, pula para próximo
                cooldown_cand_ts = getattr(self, "cooldowns_por_ativo", {}).get(cand_ativo, 0.0)
                cfg_micro = getattr(config, "MICRO_SCALPER_CONFIG", {})
                cooldown_s = cfg_micro.get("cooldown", {}).get("tempo_minimo_segundos", 25)
                if cooldown_cand_ts > 0 and (time.time() - cooldown_cand_ts) < cooldown_s:
                    continue

                preco_cand = getattr(self, "ultima_cotacao_por_ativo", {}).get(cand_ativo) or (
                    self.ultima_cotacao
                    if hasattr(self, "ultima_cotacao") and self.ultima_cotacao
                    else 100.0
                )

                analise_cand = self._analisar_entrada_turbo(
                    ativo=cand_ativo,
                    preco_atual=preco_cand,
                    modo=self.modo_operacao,
                    meta=self.meta_diaria,
                    lucro_atual=lucro_atual,
                    operacoes_ativas=self.operacoes_ativas_count,
                )

                if analise_cand.get("sinal", False):
                    analise = analise_cand
                    break
                else:
                    if melhor_analise_sem_sinal is None or analise_cand.get("score", 0.0) > melhor_analise_sem_sinal.get("score", 0.0):
                        melhor_analise_sem_sinal = analise_cand

            if not analise:
                analise = melhor_analise_sem_sinal or {
                    "executada": False,
                    "sinal": False,
                    "tipo": None,
                    "ativo": self.par_atual,
                    "razao": "Nenhum sinal confirmado no pool turbo",
                    "motivo_recusa": "Nenhum sinal confirmado",
                    "confianca": 0.0,
                    "score": 0.0,
                    "min_score": 85.0,
                    "estado": MicroScalperState.NORMAL,
                    "lucro_atual": lucro_atual,
                    "operacoes_ativas": self.operacoes_ativas_count,
                }

            self.ultima_telemetria_analise = analise

            # Se não há sinal em nenhum ativo, retorna a telemetria
            if not analise.get("sinal", False):
                return {
                    "executada": False,
                    "ativo": analise.get("ativo", self.par_atual),
                    "razao": analise.get("razao", "Sem sinal"),
                    "motivo_recusa": analise.get("motivo_recusa", "Sem sinal"),
                    "confianca": analise.get("confianca", 0.0),
                    "score": analise.get("score", 0.0),
                    "min_score": analise.get("min_score", 85.0),
                    "estado": analise.get("estado", MicroScalperState.NORMAL),
                    "lucro_atual": lucro_atual,
                    "operacoes_ativas": self.operacoes_ativas_count,
                }

            # Sinal aprovado com confluência determinística >= 85!
            tipo_operacao = analise.get("tipo", "CALL")
            valor_entrada = analise.get("volume", 0.35)
            ativo_sinal = analise.get("ativo", self.par_atual)

            # GATEWAY DE RISCO INVIOLÁVEL: validação final pré-ordem para o ativo do sinal
            valido_risco, motivo_risco = self.validar_gateway_risco(valor_entrada, ativo=ativo_sinal)
            if not valido_risco:
                self.logger.warning(f"🚫 Ordem bloqueada pelo gateway de risco ({ativo_sinal}): {motivo_risco}")
                sm = obter_state_machine(ativo_sinal)
                sm.transitar(MicroScalperState.NORMAL, motivo_risco)
                state_machine_micro_scalper.transitar(MicroScalperState.NORMAL, motivo_risco)
                return {
                    "executada": False,
                    "ativo": ativo_sinal,
                    "razao": motivo_risco,
                    "motivo_recusa": motivo_risco,
                    "confianca": analise.get("confianca", 0.0),
                    "score": analise.get("score", 0.0),
                    "estado": MicroScalperState.NORMAL,
                    "lucro_atual": lucro_atual,
                    "operacoes_ativas": self.operacoes_ativas_count,
                }

            # Envia ordem para a Deriv API
            sm = obter_state_machine(ativo_sinal)
            sm.transitar(
                MicroScalperState.COMPRANDO,
                f"Enviando {tipo_operacao} de ${valor_entrada:.2f} para {ativo_sinal}",
            )
            state_machine_micro_scalper.transitar(
                MicroScalperState.COMPRANDO,
                f"Enviando {tipo_operacao} de ${valor_entrada:.2f} para {ativo_sinal}",
            )
            sucesso = self.comprar(tipo_operacao, valor_entrada, ativo=ativo_sinal)

            if sucesso:
                self.logger.info(
                    f"🚀 ENTRADA EXECUTADA! {tipo_operacao} em {ativo_sinal} - ${valor_entrada:.2f} - "
                    f"Score: {analise.get('score', 0.0):.1f} - {analise.get('razao')}"
                )
                return {
                    "executada": True,
                    "tipo": tipo_operacao,
                    "ativo": ativo_sinal,
                    "valor": valor_entrada,
                    "confianca": analise.get("confianca", 0.0),
                    "score": analise.get("score", 0.0),
                    "estado": MicroScalperState.COMPRANDO,
                    "razao": analise.get("razao", "Operação executada"),
                    "lucro_esperado": valor_entrada * 0.85,
                    "lucro_atual": lucro_atual,
                    "operacoes_ativas": self.operacoes_ativas_count + 1,
                }
            else:
                sm.transitar(MicroScalperState.NORMAL, "Falha na API ao comprar")
                state_machine_micro_scalper.transitar(MicroScalperState.NORMAL, "Falha na API ao comprar")
                return {
                    "executada": False,
                    "ativo": ativo_sinal,
                    "razao": "Falha ao enviar ordem para a Deriv API",
                    "motivo_recusa": "Falha de comunicação WebSocket / API",
                    "confianca": analise.get("confianca", 0.0),
                    "score": analise.get("score", 0.0),
                    "estado": MicroScalperState.NORMAL,
                    "lucro_atual": lucro_atual,
                    "operacoes_ativas": self.operacoes_ativas_count,
                }

        except Exception as e:
            self.logger.error(f"Erro na execução inteligente: {str(e)}", exc_info=True)
            return {
                "executada": False,
                "razao": f"Erro interno: {str(e)}",
                "confianca": 0.0,
                "lucro_atual": self.obter_saldo() - self.saldo_inicial,
                "operacoes_ativas": len(self.operacoes_abertas),
            }

    def verificar_protecao_parada(self) -> dict:
        """Verifica se pode parar o robô com segurança."""
        try:
            lucro_atual = self.obter_saldo() - self.saldo_inicial
            operacoes_lista = list(self.operacoes_abertas.values())

            return self.catalogador.verificar_protecao_operacoes(
                operacoes_abertas=operacoes_lista,
                meta=self.meta_diaria,
                lucro_atual=lucro_atual,
            )
        except Exception as e:
            self.logger.error(f"Erro na verificação de proteção: {str(e)}")
            return {
                "pode_parar": True,
                "razao": "Erro na análise, parando por segurança",
            }

    async def executar_operacao(self, tipo: str, valor: float):
        # Validação de risco integrada
        validacao = self.gestao_riscos.validar_operacao(
            valor, getattr(self, "modo_operacao", "conservador"), self.obter_saldo()
        )

        if not validacao["permitido"]:
            self.log_unificado(
                f"❌ Operação bloqueada: {validacao['razao']}", "warning", "risco"
            )
            return False

        self.log_unificado(
            f"✅ Operação aprovada: {tipo} ${valor:.2f} (Risco: {validacao.get('risco_calculado', 0):.1f}%)",
            "trading",
            "motor",
        )

        # Registra operação como aberta
        self.gestao_riscos.registrar_operacao(
            {
                "tipo": tipo,
                "valor": valor,
                "status": "aberta",
                "timestamp": datetime.now().isoformat(),
                "saldo_antes": self.obter_saldo(),
            }
        )

        return True

    def registrar_resultado_operacao(
        self, tipo: str, valor: float, resultado: float
    ) -> None:
        """Registra o resultado de uma operação para análise de risco"""
        try:
            self.gestao_riscos.registrar_operacao(
                {
                    "tipo": tipo,
                    "valor": valor,
                    "resultado": resultado,
                    "status": "fechada",
                    "timestamp": datetime.now().isoformat(),
                    "saldo_antes": self.obter_saldo() - resultado,
                    "saldo_depois": self.obter_saldo(),
                }
            )

            # Log do resultado
            if resultado > 0:
                self.log_unificado(
                    f"✅ WIN: {tipo} | Entrada: ${valor:.2f} | Lucro: ${resultado:.2f}",
                    "success",
                    "trading",
                )
            else:
                self.log_unificado(
                    f"❌ LOSS: {tipo} | Entrada: ${valor:.2f} | Perda: ${abs(resultado):.2f}",
                    "warning",
                    "trading",
                )

            # Verifica alertas de risco
            alertas = self.gestao_riscos.verificar_alertas(
                getattr(self, "modo_operacao", "conservador")
            )
            for alerta in alertas:
                if alerta["nivel"] == "critical":
                    self.log_unificado(
                        f"🚨 ALERTA CRÍTICO: {alerta['mensagem']}", "error", "risco"
                    )
                elif alerta["nivel"] == "warning":
                    self.log_unificado(
                        f"⚠️ ALERTA: {alerta['mensagem']}", "warning", "risco"
                    )

        except Exception as e:
            self.logger.error(f"Erro ao registrar resultado da operação: {e}")

    def comprar(self, tipo: str, valor: float, ativo: Optional[str] = None) -> bool:
        """
        ESTRATÉGIA TURBO - Envia ordem de compra para contratos de 15 segundos.
        Proteção Estrita:
        - Bloqueio total em conta REAL (SHADOW/DEMO ONLY)
        - Bloqueio em caso de parada de sessão (SESSION STOP)
        - Suporte a múltiplos ativos integrados
        """
        try:
            # Trava estrita de segurança para conta REAL
            if getattr(self, "modo_real", False):
                self.logger.error(
                    "🛑 [SAFETY LOCK] Execução em conta REAL bloqueada nesta versão "
                    "(SHADOW/DEMO ONLY: REAL_ORDER_SENT = NO, REAL_ACCOUNT_EXECUTION = BLOCKED). Nenhuma ordem enviada."
                )
                return False

            # Trava estrita de SESSION STOP
            if getattr(self, "session_stopped", False):
                self.logger.warning(
                    f"🛑 [SESSION STOP] Nova compra bloqueada: {getattr(self, 'session_stop_reason', 'Sessão encerrada')}"
                )
                return False

            with self.lock:
                if not self.ws or not self.conectado:
                    self.logger.error("Não conectado à API. Tentando reconectar...")
                    self._tentar_reconectar()
                    return False

                # Obtém símbolo alvo
                simbolo = (ativo or self.par_atual).upper().strip()

                # Obtém configurações da estratégia turbo integrada
                ativo_config = ATIVOS_TURBO_INTEGRADOS.get(simbolo)
                if not ativo_config:
                    self.logger.error(
                        f"Ativo {simbolo} não configurado para estratégia turbo"
                    )
                    return False

                # Verifica se o valor está acima do mínimo permitido
                min_stake = ativo_config.get("min_stake", 0.35)
                if valor < min_stake:
                    self.logger.error(
                        f"Valor da ordem (${valor:.2f}) abaixo do mínimo permitido para {simbolo} (${min_stake})"
                    )
                    return False

                # Determina o tipo de contrato baseado na estratégia turbo
                contract_types = ativo_config.get("contract_types", ["CALL", "PUT"])
                contract_type = (
                    contract_types[0]  # CALL
                    if tipo.lower() in ["compra", "call"]
                    else contract_types[1]  # PUT
                )

                # Registra o timestamp de início da operação
                timestamp_inicio = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Prepara o request com ID de transação para rastreabilidade
                transaction_id = f"turbo_{int(time.time())}"

                # Configura requisição para contrato turbo de 15 segundos
                if ativo_config.get("tipo_contrato") == "turbo":
                    # Contrato turbo de 15 segundos
                    req = {
                        "buy": 1,
                        "parameters": {
                            "contract_type": contract_type,
                            "symbol": simbolo,
                            "underlying_symbol": simbolo,
                            "amount": valor,
                            "basis": "stake",
                            "duration": 15,  # 15 segundos
                            "duration_unit": "s",  # segundos
                            "currency": "USD",
                        },
                        "price": valor,
                        "passthrough": {"transaction_id": transaction_id},
                    }
                else:
                    # Fallback para multiplier se turbo não disponível
                    multipliers_disponiveis = ativo_config.get("multipliers", [1, 2, 3])
                    multiplier = min(multipliers_disponiveis)  # Usa o menor multiplier

                    req = {
                        "buy": 1,
                        "parameters": {
                            "contract_type": contract_type.replace(
                                "CALL", "MULTUP"
                            ).replace("PUT", "MULTDOWN"),
                            "symbol": simbolo,
                            "underlying_symbol": simbolo,
                            "amount": valor,
                            "basis": "stake",
                            "multiplier": multiplier,
                            "currency": "USD",
                        },
                        "price": valor,
                        "passthrough": {"transaction_id": transaction_id},
                    }

                # Log da operação
                duracao_str = (
                    "15s"
                    if ativo_config.get("tipo_contrato") == "turbo"
                    else f"x{multiplier if 'multiplier' in locals() else 1}"
                )
                self.logger.info(
                    f"Enviando ordem TURBO {contract_type} ({duracao_str}) de ${valor:.2f} para {simbolo} (ID: {transaction_id})"
                )
                self.ws.send(json.dumps(req))

                # Armazena informações da transação pendente
                if not hasattr(self, "transacoes_pendentes"):
                    self.transacoes_pendentes = {}

                self.transacoes_pendentes[transaction_id] = {
                    "tipo": contract_type,
                    "valor": valor,
                    "duracao": (
                        15 if ativo_config.get("tipo_contrato") == "turbo" else 1
                    ),
                    "timestamp": timestamp_inicio,
                    "par": simbolo,
                    "processada": False,
                    "fechamento_automatico": ativo_config.get("tipo_contrato")
                    != "turbo",  # Só fecha automaticamente se não for turbo
                    "tempo_maximo_segundos": (
                        15 if ativo_config.get("tipo_contrato") == "turbo" else 1
                    ),
                }

                return True
        except Exception as e:
            self.logger.error(f"Erro ao enviar ordem: {str(e)}", exc_info=True)
            return False

    def fechar_operacao(self, contract_id=None):
        """Fecha a operação especificada ou todas as operações se não for especificado."""
        try:
            if not self.ws or not self.conectado:
                self.logger.error("Não conectado à API")
                return False

            with self.lock:
                if contract_id is None and not self.operacoes_abertas:
                    self.logger.warning("Não há operações para fechar")
                    return False

                ids_para_fechar = (
                    [contract_id]
                    if contract_id
                    else list(self.operacoes_abertas.keys())
                )

                for cid in ids_para_fechar:
                    if cid in self.operacoes_abertas:
                        req = {"sell": cid, "price": 0}
                        self.ws.send(json.dumps(req))
                        self.logger.info(f"Enviado pedido para fechar operação {cid}")

                return True
        except Exception as e:
            self.logger.error(f"Erro ao fechar operação: {str(e)}", exc_info=True)
            return False

    def _obter_config_ativo(self, ativo: str) -> dict:
        """Obtém a configuração específica do ativo"""
        # Configuração local de ativos para evitar problemas de importação
        ATIVOS_SCALPING = {
            "1HZ75V": {
                "min_stake": 0.35,
                "multipliers": [10, 100, 200, 300, 400],
                "contract_types": ["CALL", "PUT"],
                "basis": "stake",
                "duracao_padrao": 15,
                "tipo_contrato": "turbo",
            },
            "1HZ100V": {
                "min_stake": 0.35,
                "multipliers": [10, 100, 200, 300, 400],
                "contract_types": ["CALL", "PUT"],
                "basis": "stake",
                "duracao_padrao": 15,
                "tipo_contrato": "turbo",
            },
            "R_10": {
                "min_stake": 0.35,
                "multipliers": [1, 2, 3, 4, 5, 10],
                "contract_types": ["MULTUP", "MULTDOWN"],
                "basis": "stake",
                "duracao_padrao": 1,
                "tipo_contrato": "multiplier",
            },
        }

        return ATIVOS_SCALPING.get(
            ativo,
            {
                "min_stake": 0.35,
                "multipliers": [1, 2, 3, 4, 5, 10],
                "contract_types": ["MULTUP", "MULTDOWN"],
                "basis": "stake",
                "duracao_padrao": 1,
                "tipo_contrato": "multiplier",
            },
        )

    def _calcular_multiplier_otimo(
        self, valor: float, multipliers_disponiveis: list
    ) -> int:
        """Calcula o multiplier ótimo baseado no valor da entrada"""
        # Para scalping ultra rápido, usamos multipliers baixos para reduzir risco
        if valor <= 1.0:
            return 1  # Multiplier mínimo para valores baixos
        elif valor <= 2.0:
            return (
                min(2, max(multipliers_disponiveis)) if multipliers_disponiveis else 2
            )
        elif valor <= 5.0:
            return (
                min(3, max(multipliers_disponiveis)) if multipliers_disponiveis else 3
            )
        else:
            return (
                min(5, max(multipliers_disponiveis)) if multipliers_disponiveis else 5
            )

    def obter_saldo(self):
        """Retorna o saldo atual da conta."""
        try:
            return self.saldo
        except Exception as e:
            self.logger.error(f"Erro ao obter saldo: {str(e)}")
            return 0.0

    def obter_id_conta(self):
        """Retorna o ID da conta autenticada."""
        if getattr(self, "account_id", None):
            return self.account_id
        if self.id_conta_real:
            return self.id_conta_real
        return None

    def obter_id_conta_forcado(self):
        """Retorna o ID da conta ativa (PAT + OTP define o account_id na conexão)."""
        acc_id = self.obter_id_conta()
        if acc_id:
            return acc_id

        # Se ainda não houver, consulta via API REST oficial
        if self.token and getattr(self, "app_id", None):
            try:
                base_url = getattr(config, "DERIV_API_BASE", "https://api.derivws.com")
                client = DerivAPIClient(base_url=base_url)
                contas = client.listar_contas(self.token, self.app_id)
                if contas:
                    conta = client.selecionar_conta_padrao(
                        contas, preferir_real=(getattr(self, "tipo_conta", "demo") == "real")
                    )
                    self.account_id = conta["account_id"]
                    self.id_conta_real = conta["account_id"]
                    return self.account_id
            except Exception as e:
                self.logger.error(f"Erro ao obter ID da conta via API REST: {e}")
        return None

    def definir_par(self, par: str) -> bool:
        """Altera o par de negociação atual."""
        try:
            # Lista de ativos válidos para scalping
            pares_validos = [
                "1HZ75V",
                "1HZ100V",
                "R_10",
                "R_25",
                "R_50",
                "R_75",
                "R_100",
            ]
            self.logger.debug(f"Lista de ativos carregada: {len(pares_validos)} ativos")
            if par not in pares_validos:
                self.logger.error(
                    f"Par inválido: {par}. Deve ser um dos: {pares_validos}"
                )
                return False

            # Cancela inscrição atual e inscreve no novo par
            if self.conectado:
                # Cancela atual
                cancel_req = {"forget_all": "ticks"}
                self.ws.send(json.dumps(cancel_req))

                # Muda par
                self.par_atual = par
                # Atualiza também no catalogador
                if hasattr(self, "catalogador") and self.catalogador:
                    self.catalogador.ativo_atual = par

                # Inscreve no novo
                return self._inscrever_ticks()
            else:
                # Apenas atualiza o par, inscrição será feita quando conectar
                self.par_atual = par
                # Atualiza também no catalogador
                if hasattr(self, "catalogador") and self.catalogador:
                    self.catalogador.ativo_atual = par
                return True
        except Exception as e:
            self.logger.error(f"Erro ao definir par: {str(e)}", exc_info=True)
            return False

    def obter_historico(self) -> List[Dict]:
        """Retorna o histórico de operações."""
        try:
            with self.lock:
                return self.historico_operacoes.copy()
        except Exception as e:
            self.logger.error(f"Erro ao obter histórico: {str(e)}")
            return []

    def desconectar(self):
        """Fecha a conexão com a API e limpa subscrições de ticks."""
        try:
            if self.ws:
                self.logger.info("Desconectando WebSocket e cancelando subscrições...")
                try:
                    self.ws.send(json.dumps({"forget_all": "ticks"}))
                except Exception:
                    pass
                self.ws.close()
                self.ws = None
            self.tick_subscription_id_por_ativo.clear()
            self.conectado = False
        except Exception as e:
            self.logger.error(f"Erro ao desconectar: {str(e)}")

    def _agendar_reconexao(self):
        """Agenda reconexão inteligente sem loops."""
        if hasattr(self, "_ultima_reconexao"):
            tempo_desde_ultima = time.time() - self._ultima_reconexao
            if tempo_desde_ultima < 30:  # Não reconecta se foi há menos de 30s
                return

        self._ultima_reconexao = time.time()

        def reconectar_inteligente():
            time.sleep(5)  # Aguarda 5 segundos
            try:
                self.logger.info("[RECONEXAO] Solicitando novo OTP para reconexão...")
                account_id = getattr(self, "account_id", None)
                tipo_c = getattr(self, "tipo_conta", "demo")
                app_id = getattr(self, "app_id", None)
                if self.conectar(token=self.token, account_id=account_id, account_type=tipo_c, app_id=app_id):
                    self.logger.info("Reconexão inteligente com novo OTP bem-sucedida")
                else:
                    self.logger.warning("Reconexão inteligente falhou")
            except Exception as e:
                self.logger.error(f"Erro na reconexão inteligente: {e}")

        thread = threading.Thread(target=reconectar_inteligente, daemon=True)
        thread.start()

    def _tentar_reconectar(self):
        """RECONEXÃO AUTOMÁTICA DESABILITADA."""
        pass

    def _iniciar_verificador_conexao(self):
        """Inicia thread para verificar conexão periodicamente."""

        def verificar_conexao():
            while True:
                try:
                    # Evita verificar se já estamos tentando reconectar
                    if self.reconectado_recentemente:
                        time.sleep(self.intervalo_verificacao)
                        continue

                    # Verifica timeout de inatividade
                    agora = time.time()
                    if (
                        self.conectado
                        and agora - self.ultima_mensagem_recebida > self.max_inatividade
                    ):
                        self.logger.warning(
                            f"Inatividade detectada: {int(agora - self.ultima_mensagem_recebida)}s sem mensagens."
                        )
                        # RECONEXÃO AUTOMÁTICA DESABILITADA

                    # Pausa entre verificações
                    time.sleep(self.intervalo_verificacao)
                except Exception as e:
                    self.logger.error(f"Erro no verificador de conexão: {str(e)}")
                    time.sleep(
                        self.intervalo_verificacao * 2
                    )  # Pausa maior em caso de erro

        # Inicia thread de verificação
        if not self.verificando_conexao:
            self.verificando_conexao = True
            thread = threading.Thread(target=verificar_conexao)
            thread.daemon = True
            thread.start()

    def _fechar_operacao_por_stop(self, contract_id: str, verificacao_stop: dict):
        """Fecha uma operação devido a stop loss ou take profit"""
        try:
            if contract_id not in self.operacoes_abertas:
                return

            # Envia comando para fechar a operação
            req = {"sell": contract_id, "price": 0}  # Vende pelo preço atual de mercado

            if self.ws and self.conectado:
                self.ws.send(json.dumps(req))
                self.log_unificado(
                    f"🛑 Stop {verificacao_stop['tipo']}: {verificacao_stop['razao']}",
                    "warning",
                    "stops",
                )
            else:
                self.logger.warning(
                    f"Não foi possível fechar operação {contract_id}: não conectado"
                )

        except Exception as e:
            self.logger.error(f"Erro ao fechar operação por stop: {e}")

    def _verificar_fechamento_automatico(self):
        """
        Watchdog de Segurança para Operações Abertas.
        Monitora se o contrato excedeu o tempo máximo de retenção (max_hold_seconds)
        e dispara fechamento de emergência caso a API não tenha finalizado.
        NUNCA fecha cegamente após 1 segundo.
        """
        agora = time.time()
        try:
            if not self.operacoes_abertas:
                return

            cfg_saida = getattr(config, "MICRO_SCALPER_CONFIG", {}).get("saida", {})
            max_hold_s = cfg_saida.get("max_hold_seconds", 45)

            for contract_id, operacao in list(self.operacoes_abertas.items()):
                timestamp_abertura = operacao.get("timestamp_abertura", agora)
                tempo_decorrido = agora - timestamp_abertura

                # Se ultrapassou o tempo limite de segurança, força fechamento
                if tempo_decorrido >= max_hold_s:
                    self.logger.warning(
                        f"⚠️ Watchdog: Operação {contract_id} atingiu tempo máximo de retenção "
                        f"({tempo_decorrido:.1f}s >= {max_hold_s}s). Disparando fechamento..."
                    )
                    operacao["motivo_saida"] = "MAX_HOLD_WATCHDOG"
                    self.fechar_operacao(contract_id)

        except Exception as e:
            self.logger.error(
                f"Erro no watchdog de operações: {str(e)}", exc_info=True
            )

    def status_conexao(self):
        """Retorna o status atual da conexão com a Deriv."""
        try:
            status_flag = "ok" if self.conectado else "erro"
            resposta = {"status": status_flag}

            if status_flag == "ok":
                resposta["mensagem"] = "Conectado com sucesso"
                resposta["saldo"] = self.obter_saldo()
                resposta["conta_tipo"] = "Demo" if not self.modo_real else "Real"
                resposta["conta_moeda"] = "USD"
            else:
                resposta["mensagem"] = (
                    self.ultimo_erro or "Falha na conexão com a Deriv"
                )

            return resposta
        except Exception as e:
            self.logger.error(f"Erro ao verificar status: {str(e)}")
            return {"status": "erro", "mensagem": f"Erro interno: {str(e)}"}

    def iniciar(self):
        """Inicia o motor de trading"""
        if not self.conectado:
            if not self.conectar(self.token):
                return False

        self.rodando = True
        self.logger.info("Motor iniciado")
        return True

    def parar(self):
        """Para o motor de trading"""
        self.rodando = False

        # Fecha operações ativas
        for op_id in list(self.operacoes_abertas.keys()):
            self.fechar_operacao(op_id)

        self.logger.info("Motor parado")

    def set_modo(self, modo: str):
        """Define modo de operação"""
        self.modo_real = modo.lower()
        self.logger.info(f"Modo alterado para: {self.modo_real}")

    def get_status(self) -> Dict[str, Any]:
        """Retorna status atual"""
        return {
            "conectado": self.conectado,
            "rodando": self.rodando,
            "saldo": self.obter_saldo(),
            "modo": self.modo_real,
            "operacoes_ativas": len(self.operacoes_abertas),
            "historico": len(self.obter_historico()),
        }

    def iniciar_sistema_inteligente(self):
        """Inicia o sistema inteligente de operações em thread separada"""
        import threading

        def executar_loop_inteligente():
            """Loop principal do sistema inteligente"""
            self.logger.info("Sistema inteligente de operações iniciado")

            # Envia log para a UI
            try:
                import main

                main.adicionar_log_tempo_real("Sistema inteligente iniciado", "success")
                main.adicionar_log_tempo_real(
                    f"Analisando {self.par_atual} para scalping", "info"
                )
            except:
                pass

            # Marca como rodando
            self.rodando = True

            # Loop principal - continua enquanto o robô estiver ativo
            while self.rodando and hasattr(self, "conectado"):
                try:
                    if not self.conectado:
                        self.logger.warning(
                            "Motor desconectado - reconexão automática desabilitada"
                        )
                        time.sleep(10)
                        continue

                    # Se a sessão foi finalizada (meta, perda, erro crítico ou kill switch):
                    if getattr(self, "session_stopped", False):
                        if len(self.operacoes_abertas) == 0:
                            self.logger.info(
                                f"🏁 Sessão finalizada ({getattr(self, 'session_stop_reason', 'STOP')}). "
                                "Todas as operações foram concluídas e conciliadas com sucesso."
                            )
                            self.rodando = False
                            break
                        else:
                            self.logger.info(
                                f"⏳ Sessão parada ({getattr(self, 'session_stop_reason', 'STOP')}). "
                                f"Aguardando encerramento de {len(self.operacoes_abertas)} operações ativas..."
                            )
                            time.sleep(1.0)
                            continue

                    # Executa análise e operação inteligente
                    resultado = self.executar_operacao_inteligente()

                    if resultado["executada"]:
                        self.logger.info(
                            f"OPERACAO {resultado['tipo']} EXECUTADA em {resultado.get('ativo', self.par_atual)} - "
                            f"Conf: {resultado['confianca']:.2f} - "
                            f"{resultado['razao']}"
                        )
                    else:
                        # Log normal para acompanhar análises
                        self.logger.info(f"ANALISE: {resultado['razao']}")

                    # Se a sessão parou durante a execução e não há mais posições abertas
                    if getattr(self, "session_stopped", False) and len(self.operacoes_abertas) == 0:
                        self.logger.info(f"🏁 Sessão finalizada: {getattr(self, 'session_stop_reason', 'STOP')}")
                        self.rodando = False
                        break

                    # Verifica se atingiu a meta
                    if resultado["lucro_atual"] >= self.meta_diaria:
                        self.logger.info(
                            f"META DE ${self.meta_diaria:.2f} ATINGIDA! "
                            f"Lucro: ${resultado['lucro_atual']:.2f}"
                        )
                        self.session_stopped = True
                        self.session_stop_reason = f"META_ATINGIDA: Lucro ${resultado['lucro_atual']:.2f} >= ${self.meta_diaria:.2f}"
                        if len(self.operacoes_abertas) == 0:
                            self.rodando = False
                            break

                    # Intervalos calibrados para ativos de 1 segundo
                    intervalo = {
                        "iniciante": 1.0,    # 1 segundo - ativos 1s exigem análise rápida
                        "intermediario": 0.8, # 800ms - moderado
                        "conservador": 0.8,   # 800ms - moderado
                        "agressivo": 0.4,    # 400ms - máxima velocidade
                    }.get(self.modo_operacao, 1.0)

                    time.sleep(intervalo)

                except Exception as e:
                    self.logger.error(
                        f"Erro no sistema inteligente: {str(e)}", exc_info=True
                    )
                    time.sleep(5)

            self.logger.info("Sistema inteligente de operações finalizado")

        # Inicia thread do sistema inteligente
        thread = threading.Thread(target=executar_loop_inteligente, daemon=True)
        thread.start()
        self.logger.info("Thread do sistema inteligente iniciada")

    def registrar_log(self, mensagem: str, tipo: str = "info"):
        """Registra um log com timestamp"""
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S.%f")[:-3]

        log_entry = {
            "timestamp": timestamp,
            "tipo": tipo,
            "mensagem": mensagem,
            "emoji": self._get_emoji(tipo),
        }

        self.logs.append(log_entry)
        self.logger.info(f"{log_entry['emoji']} {mensagem}")

        # Manter apenas últimos 100 logs
        if len(self.logs) > 100:
            self.logs.pop(0)

        return log_entry

    def _get_emoji(self, tipo: str) -> str:
        """Retorna emoji baseado no tipo de log"""
        emojis = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "analysis": "🔍",
            "mode": "🔄",
            "trade": "💰",
        }
        return emojis.get(tipo, "📝")

    async def reconectar(self):
        """Sistema robusto de reconexão"""
        for _ in range(self.max_reconexoes):
            try:
                await self._conectar()
                return True
            except Exception:
                await asyncio.sleep(self.delay_reconexao)
        return False
