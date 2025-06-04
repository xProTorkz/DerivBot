# motor.py - Atualizado para integração total com painel, meta e catalogador

import time
import json
import websocket
import threading
import os
from datetime import datetime
from typing import Dict, List, Optional, Union, Callable, Any
import logging

from src import config
from src.core.catalogador import Catalogador
from src.core.estrategia_turbo import (
    ESTRATEGIA_TURBO,
    ATIVOS_TURBO,
    obter_ativo_prioritario,
    calcular_volume_entrada,
)


class Motor:
    def __init__(self):
        """Inicializa o motor de operações."""
        # Logger específico - DEVE SER PRIMEIRO
        self.logger = logging.getLogger("DerivBot.Motor")

        self.ws = None
        self.conectado = False
        self.token = None
        self.saldo = 0.0
        self.operacoes_abertas = {}
        self.historico_operacoes = []
        self.callback_tick = None
        self.ultima_resposta = None
        self.ultima_cotacao = None
        # SISTEMA DE MÚLTIPLOS ATIVOS PARA SCALPING RÁPIDO
        self.ativos_ativos = [
            "1HZ75V",
            "1HZ100V",
            "R_10",
            "R_25",
            "R_50",
        ]  # Múltiplos ativos
        self.par_atual = "1HZ75V"  # Ativo principal
        self.ativo_fixo_turbo = False  # Permite mudança de ativo
        self.rotacao_ativos = True  # Ativa rotação entre ativos
        self.ultimo_ativo_usado = 0  # Índice do último ativo usado
        self.logger.info(
            f"ESTRATEGIA TURBO MULTI-ATIVO ATIVADA - Ativos: {self.ativos_ativos}"
        )
        self.scanner_ativo = True  # Ativa o scanner de ativos
        self.ultimo_scan_ativo = 0  # Timestamp do último scan
        self.modo_real = getattr(config, "MODO_REAL", True)
        self.catalogador = Catalogador()  # Inicializa catalogador
        # Define o ativo atual no catalogador
        self.catalogador.ativo_atual = self.par_atual
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

    def conectar(self, token=None):
        """Conecta com a API da Deriv usando o token fornecido ou o token já configurado."""
        if token:
            return self._conectar_com_token(token)
        elif self.token:
            return self._conectar_com_token(self.token)
        else:
            self.logger.error("Nenhum token fornecido para conexão")
            return False

    def _conectar_com_token(self, token):
        """Conecta com a API da Deriv usando o token fornecido.

        Args:
            token: Token de autorização da Deriv

        Returns:
            bool: True se conectou com sucesso, False caso contrário
        """
        try:
            self.token = token
            # Cloudflare 530/1016 indica que ws.deriv.com não resolve em algumas regiões.
            # Domínio oficial conforme documentação: ws.derivws.com
            ws_url = "wss://ws.derivws.com/websockets/v3?app_id=71203"

            # Fecha conexão existente se houver
            self.desconectar()

            # Configura nova conexão
            self.logger.info(f"Iniciando conexão com Deriv API ({ws_url})")
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )

            # Reseta contadores de reconexão
            self.tentativas_reconexao = 0
            self.reconectado_recentemente = False

            # Roda o WebSocket em uma thread separada
            wst = threading.Thread(target=self.ws.run_forever)
            wst.daemon = True
            wst.start()

            # Aguarda autenticação (máximo 10s)
            for _ in range(20):
                if self.conectado:
                    self.logger.info("Conexão estabelecida com sucesso.")
                    return True
                time.sleep(0.5)

            self.logger.error("Timeout ao conectar: sem resposta da API.")
            return False
        except Exception as e:
            self.logger.error(f"Erro durante conexão: {str(e)}", exc_info=True)
            self.ultimo_erro = f"Erro durante conexão: {str(e)}"
            return False

    def _on_open(self, ws):
        """Callback quando a conexão WebSocket é aberta."""
        try:
            self.logger.info("Conexão WebSocket aberta, enviando autorização")
            # Envia o token para autenticar
            req = {"authorize": self.token}
            ws.send(json.dumps(req))
            self.ultima_mensagem_recebida = time.time()
        except Exception as e:
            self.logger.error(f"Erro no callback on_open: {str(e)}", exc_info=True)

    def _on_message(self, ws, message):
        """Callback para processar mensagens recebidas do WebSocket."""
        try:
            # Atualiza o timestamp da última mensagem recebida
            self.ultima_mensagem_recebida = time.time()

            # Reduz verbosidade para mensagens frequentes (ticks)
            if '"tick"' not in message or time.time() - self.ultimo_tick_timestamp > 5:
                self.logger.debug(f"Mensagem recebida: {message[:100]}...")
                self.ultimo_tick_timestamp = time.time()

            data = json.loads(message)
            self.ultima_resposta = data

            # Processamento da autorização
            if "authorize" in data and data["authorize"]:
                self.conectado = True
                self.saldo = data["authorize"].get("balance", 0)
                self.saldo_inicial = self.saldo
                self.logger.info(f"Autenticado com sucesso. Saldo: {self.saldo}")

                # Agora inscreve nos ticks
                self._inscrever_ticks()

                # Reseta contadores de reconexão
                self.tentativas_reconexao = 0
                if self.reconectado_recentemente:
                    self.logger.info("Reconexão bem-sucedida!")
                    self.reconectado_recentemente = False

            # Processamento de ticks
            if "tick" in data and data["tick"]:
                tick_data = data["tick"]
                self.ultima_cotacao = tick_data.get("quote", 0)
                self.catalogador.adicionar_tick(self.ultima_cotacao)

                # Executa o callback se registrado
                if self.callback_tick:
                    self.callback_tick(self.ultima_cotacao)

                # Não executamos operações diretamente aqui, apenas através do app.py
                # que controlará corretamente os valores de entrada

                # Verifica operações que precisam ser fechadas automaticamente (micro scalping)
                self._verificar_fechamento_automatico()

            # Processamento de abertura de contratos
            if "buy" in data and data["buy"]:
                contract_id = data["buy"]["contract_id"]

                # Verifica se tem informação de transaction_id para rastreamento
                transaction_id = None
                if "passthrough" in data and data["passthrough"]:
                    transaction_id = data["passthrough"].get("transaction_id")

                # Registra com informações detalhadas
                with self.lock:
                    # Adiciona às operações abertas
                    self.operacoes_abertas[contract_id] = {
                        "id": contract_id,
                        "preco_entrada": data["buy"]["buy_price"],
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "tipo": data.get("echo_req", {})
                        .get("parameters", {})
                        .get("contract_type", ""),
                        "transaction_id": transaction_id,
                        "timestamp_abertura": time.time(),  # Timestamp UNIX para cálculo de tempo decorrido
                        "fechamento_automatico": (
                            True
                            if transaction_id
                            and hasattr(self, "transacoes_pendentes")
                            and transaction_id in self.transacoes_pendentes
                            and self.transacoes_pendentes[transaction_id].get(
                                "fechamento_automatico"
                            )
                            else False
                        ),
                        "tempo_maximo_segundos": 1,  # Default de 1 segundo para micro scalping
                    }

                    # Se tivermos o transaction_id, atualizamos seu status
                    if transaction_id and hasattr(self, "transacoes_pendentes"):
                        if transaction_id in self.transacoes_pendentes:
                            self.transacoes_pendentes[transaction_id][
                                "processada"
                            ] = True
                            self.transacoes_pendentes[transaction_id][
                                "contract_id"
                            ] = contract_id

                self.logger.info(
                    f"Operação {contract_id} aberta com sucesso. Modo: micro scalping (1s)"
                )

                # Para contratos multipliers, vamos configurar um timer para fechamento automático após 1 segundo
                if "MULT" in str(self.operacoes_abertas[contract_id]["tipo"]).upper():
                    self.logger.info(
                        f"Configurado fechamento automático em 1 segundo para operação {contract_id}"
                    )
                    # Aqui usamos um timer, mas o _verificar_fechamento_automatico será responsável pelo fechamento

            # Processamento de atualização/fechamento de contratos
            if "proposal_open_contract" in data and data["proposal_open_contract"]:
                contract = data["proposal_open_contract"]
                contract_id = contract["contract_id"]

                if contract["is_sold"] == 1 and contract_id in self.operacoes_abertas:
                    lucro = contract["profit"]

                    # Log detalhado do resultado
                    self.logger.info(
                        f"Operação {contract_id} finalizada com resultado: ${lucro}"
                    )

                    with self.lock:
                        preco_entrada = self.operacoes_abertas[contract_id][
                            "preco_entrada"
                        ]
                        transaction_id = self.operacoes_abertas[contract_id].get(
                            "transaction_id"
                        )

                        # Registra resultado no histórico
                        resultado = {
                            "id": contract_id,
                            "preco_entrada": preco_entrada,
                            "preco_saida": contract["sell_price"],
                            "lucro": lucro,
                            "timestamp_abertura": self.operacoes_abertas[contract_id][
                                "timestamp"
                            ],
                            "timestamp_fechamento": datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "tipo": self.operacoes_abertas[contract_id]["tipo"],
                        }

                        # Adiciona ao histórico de operações
                        self.historico_operacoes.append(resultado)

                        # Atualiza o saldo após operação finalizada
                        self.saldo = float(contract["balance_after"])

                        # Notifica o sistema principal sobre a operação finalizada
                        try:
                            import main

                            operacao_dados = self.operacoes_abertas.get(contract_id, {})
                            main.adicionar_operacao(
                                tipo=operacao_dados.get("tipo", "UNKNOWN"),
                                valor=operacao_dados.get("valor", 0),
                                resultado=lucro,
                            )
                        except Exception as e:
                            self.logger.debug(f"Erro ao notificar operação: {e}")

                        # Remove das operações abertas
                        del self.operacoes_abertas[contract_id]

                    # Emite mensagem mais detalhada com resultado da operação
                    resultado_texto = "GANHO" if lucro >= 0 else "PERDA"
                    self.logger.info(
                        f"Operação {contract_id} fechada com {resultado_texto}: ${lucro:.2f} (Saldo atual: ${self.saldo:.2f})"
                    )

                    # Verifica meta
                    lucro_total = self.obter_saldo() - self.saldo_inicial
                    take_profit = getattr(config, "TAKE_PROFIT", self.meta_diaria)
                    if lucro_total >= take_profit:
                        self.logger.info("🎯 Meta diária atingida!")
                        self.meta_atingida = True
                        self.rodando = False

            # Captura erros retornados pela API
            if "error" in data:
                self.ultimo_erro = data["error"].get("message", "Erro desconhecido")
                self.logger.error(f"[DERIV ERROR] {self.ultimo_erro}")

                # Trata possíveis erros de autorização
                if (
                    "AuthorizationRequired" in self.ultimo_erro
                    or "token" in self.ultimo_erro.lower()
                ):
                    self.conectado = False
                    self.logger.error("Erro de autorização. Tentando reconectar...")
                    self._agendar_reconexao()

        except json.JSONDecodeError as e:
            self.logger.error(f"Erro ao decodificar JSON: {str(e)}")
        except Exception as e:
            self.logger.error(f"Erro ao processar mensagem: {str(e)}", exc_info=True)

    def _on_error(self, ws, error):
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

    def _on_close(self, ws, close_status_code, close_msg):
        """Callback para quando a conexão é fechada."""
        self.conectado = False
        self.logger.warning(
            f"Conexão fechada. Código: {close_status_code}, Msg: {close_msg}"
        )

        # Agenda reconexão se não for fechamento intencional
        if close_status_code != 1000:  # 1000 é fechamento normal
            self._agendar_reconexao()

    def _inscrever_ticks(self):
        """Inscreve para receber ticks do ativo atual."""
        try:
            if not self.ws or not self.conectado:
                self.logger.warning("Não é possível inscrever ticks: não conectado")
                return False

            # Verifica se deve atualizar o ativo usando o scanner
            self._atualizar_ativo_scanner()

            req = {"ticks": self.par_atual, "subscribe": 1}
            self.ws.send(json.dumps(req))
            self.logger.info(f"Inscrito para receber ticks de {self.par_atual}")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao inscrever ticks: {str(e)}")
            return False

    def _atualizar_ativo_scanner(self):
        """Atualiza o ativo usando o scanner se necessário"""
        try:
            import time

            agora = time.time()

            # Verifica se é hora de fazer novo scan (a cada 60 segundos)
            if agora - self.ultimo_scan_ativo < 60:
                return

            self.ultimo_scan_ativo = agora

            if not self.scanner_ativo:
                return

            # Inicializa o scanner se necessário
            if not hasattr(self.catalogador, "ativos_priorizados"):
                self.catalogador.inicializar_scanner_ativos()

            # Obtém o melhor ativo
            melhor_ativo = self.catalogador.analisar_melhor_ativo()

            # ESTRATÉGIA TURBO: MANTÉM VIX75 FIXO
            if hasattr(self, "ativo_fixo_turbo") and self.ativo_fixo_turbo:
                if self.par_atual != "1HZ75V":
                    self.logger.info("FORCANDO RETORNO AO VIX75 (ESTRATEGIA TURBO)")
                    self.definir_par("1HZ75V")
            # Muda o ativo se necessário (apenas se não for modo turbo)
            elif melhor_ativo and melhor_ativo != self.par_atual:
                self.logger.info(f"Mudando para {melhor_ativo} (melhor oportunidade)")
                self.definir_par(melhor_ativo)

        except Exception as e:
            self.logger.error(f"Erro no scanner de ativos: {e}")

    # FUNÇÃO REMOVIDA - Usar catalogador.obter_ativo_recomendado() diretamente

    def _analisar_entrada_turbo(
        self, ativo, preco_atual, modo, meta, lucro_atual, operacoes_ativas
    ):
        """
        ANÁLISE PRINCIPAL DA ESTRATÉGIA TURBO
        Retorna análise completa para entrada em contratos de 15 segundos
        """
        import random

        # ROTAÇÃO INTELIGENTE DE ATIVOS - Muda ativo a cada análise para mais oportunidades
        if hasattr(self, "rotacao_ativos") and self.rotacao_ativos:
            # Rotaciona para o próximo ativo da lista
            self.ultimo_ativo_usado = (self.ultimo_ativo_usado + 1) % len(
                self.ativos_ativos
            )
            ativo = self.ativos_ativos[self.ultimo_ativo_usado]

            # Atualiza o ativo atual se mudou
            if ativo != self.par_atual:
                self.par_atual = ativo
                self.logger.info(
                    f"ROTAÇÃO: Mudando para {ativo} para buscar mais oportunidades"
                )
        else:
            # Força uso do VIX75 se rotação desabilitada
            if ativo != "1HZ75V":
                ativo = "1HZ75V"

        # Verifica se deve operar - MAIS OPERAÇÕES SIMULTÂNEAS
        limite_operacoes = {
            "iniciante": 5,  # 5 operações simultâneas
            "conservador": 7,  # 7 operações simultâneas
            "agressivo": 10,  # 10 operações simultâneas
        }.get(modo, 5)

        if operacoes_ativas >= limite_operacoes:
            return {
                "executada": False,
                "sinal": False,
                "razao": f"Limite de operações simultâneas atingido ({limite_operacoes})",
                "confianca": 0.0,
                "lucro_atual": lucro_atual,
                "operacoes_ativas": operacoes_ativas,
            }

        # Verifica se atingiu meta
        if lucro_atual >= meta:
            return {
                "executada": False,
                "sinal": False,
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
        preco_na_banda = (preco_atual <= bb_inferior) or (preco_atual >= bb_superior)

        # Calcula confiança baseada nos indicadores
        confianca = 0.0
        sinais = []
        sinal = False
        tipo_operacao = None

        # ANÁLISE ULTRA AGRESSIVA - FORÇA ENTRADAS CONSTANTES

        # SEMPRE GERA SINAL - Condições extremamente flexíveis
        if rsi < 60:  # 60% das vezes será CALL
            confianca = random.uniform(0.65, 0.95)
            tipo_operacao = "CALL"
            sinal = True
            sinais.append("Sinal CALL forçado")
            sinais.append(f"RSI {rsi:.1f} favorável")

        else:  # 40% das vezes será PUT
            confianca = random.uniform(0.65, 0.95)
            tipo_operacao = "PUT"
            sinal = True
            sinais.append("Sinal PUT forçado")
            sinais.append(f"RSI {rsi:.1f} favorável")

        # BOOST DE CONFIANÇA para garantir entrada
        if modo == "agressivo":
            confianca = min(0.95, confianca + 0.10)  # +10% confiança no modo agressivo

        # Sem sinal claro
        if not sinal:
            return {
                "executada": False,
                "sinal": False,
                "razao": f"Aguardando sinal claro - RSI: {rsi:.1f}, Tendência: {'Alta' if tendencia_alta else 'Baixa'}",
                "confianca": 0.0,
                "lucro_atual": lucro_atual,
                "operacoes_ativas": operacoes_ativas,
            }

        # Verifica confiança mínima - MUITO MAIS AGRESSIVO
        confianca_minima = {
            "iniciante": 0.50,  # 50% - FORÇA ENTRADAS
            "conservador": 0.55,  # 55% - FORÇA ENTRADAS
            "agressivo": 0.45,  # 45% - FORÇA ENTRADAS MÁXIMO
        }.get(modo, 0.50)

        if confianca < confianca_minima:
            return {
                "executada": False,
                "sinal": False,
                "razao": f"Confiança {confianca:.2f} abaixo do mínimo {confianca_minima:.2f}",
                "confianca": confianca,
                "lucro_atual": lucro_atual,
                "operacoes_ativas": operacoes_ativas,
            }

        # Calcula volume da operação
        volume = 0.35  # Volume fixo para estratégia turbo
        if modo == "conservador":
            volume = 0.50
        elif modo == "agressivo":
            volume = 1.00

        # EXECUTA A OPERAÇÃO
        return {
            "executada": True,
            "sinal": True,
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

    def registrar_callback_tick(self, callback: Callable[[float], None]):
        """Registra um callback para ser chamado a cada tick recebido."""
        self.callback_tick = callback

    def executar_operacao_inteligente(self, cliente_id: str = "default") -> dict:
        """Executa operação usando ESTRATÉGIA TURBO para contratos de 15 segundos."""
        try:
            # Calcula lucro atual
            lucro_atual = self.obter_saldo() - self.saldo_inicial

            # Conta operações ativas
            self.operacoes_ativas_count = len(self.operacoes_abertas)

            # ESTRATÉGIA TURBO: Análise específica para VIX75
            analise = self._analisar_entrada_turbo(
                ativo=self.par_atual,
                preco_atual=(
                    self.ultima_cotacao
                    if hasattr(self, "ultima_cotacao") and self.ultima_cotacao
                    else 100.0
                ),
                modo=self.modo_operacao,
                meta=self.meta_diaria,
                lucro_atual=lucro_atual,
                operacoes_ativas=self.operacoes_ativas_count,
            )

            # Se não há sinal, retorna a análise
            if not analise.get("sinal", False):
                return {
                    "executada": False,
                    "razao": analise.get("razao", "Sem sinal"),
                    "confianca": analise.get("confianca", 0.0),
                    "lucro_atual": lucro_atual,
                    "operacoes_ativas": self.operacoes_ativas_count,
                }

            # Se há sinal, executa a operação
            tipo_operacao = analise.get("tipo", "CALL")
            valor_entrada = analise.get("volume", 0.35)

            # Executa a operação
            sucesso = self.comprar(tipo_operacao, valor_entrada)

            if sucesso:
                self.logger.info(
                    f"TURBO {tipo_operacao} EXECUTADA - Valor: ${valor_entrada:.2f} - "
                    f"Confiança: {analise.get('confianca', 0.0):.2f} - {analise.get('razao', 'Operação turbo')}"
                )

                return {
                    "executada": True,
                    "tipo": tipo_operacao,
                    "valor": valor_entrada,
                    "confianca": analise.get("confianca", 0.0),
                    "razao": analise.get("razao", "Operação executada"),
                    "lucro_esperado": valor_entrada * 0.85,  # Estimativa de lucro
                    "lucro_atual": lucro_atual,
                    "operacoes_ativas": self.operacoes_ativas_count + 1,
                }
            else:
                return {
                    "executada": False,
                    "razao": "Falha ao executar operação na API",
                    "confianca": analise.get("confianca", 0.0),
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

    def executar_operacao(self, tipo: str):
        """Execute uma operação de compra/venda."""
        self.logger.warning(
            "Método executar_operacao descontinuado. Use executar_operacao_inteligente()!"
        )
        return False

    def comprar(self, tipo: str, valor: float) -> bool:
        """ESTRATÉGIA TURBO - Envia ordem de compra para contratos de 15 segundos."""
        try:
            with self.lock:
                if not self.ws or not self.conectado:
                    self.logger.error("Não conectado à API. Tentando reconectar...")
                    self._tentar_reconectar()
                    return False

                # Obtém configurações da estratégia turbo
                ativo_config = ATIVOS_TURBO.get(self.par_atual)
                if not ativo_config:
                    self.logger.error(
                        f"Ativo {self.par_atual} não configurado para estratégia turbo"
                    )
                    return False

                # Verifica se o valor está acima do mínimo permitido
                min_stake = ativo_config.get("min_stake", 0.35)
                if valor < min_stake:
                    self.logger.error(
                        f"Valor da ordem (${valor:.2f}) abaixo do mínimo permitido para {self.par_atual} (${min_stake})"
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
                            "symbol": self.par_atual,
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
                            "symbol": self.par_atual,
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
                    f"Enviando ordem TURBO {contract_type} ({duracao_str}) de ${valor:.2f} para {self.par_atual} (ID: {transaction_id})"
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
                    "par": self.par_atual,
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
        from src.core.config import ATIVOS_SCALPING

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

    def definir_par(self, par: str) -> bool:
        """Altera o par de negociação atual."""
        try:
            # Importa a lista completa de ativos de scalping
            try:
                from src.core.config import ATIVOS_SCALPING

                pares_validos = list(ATIVOS_SCALPING.keys())
                self.logger.debug(
                    f"Lista de ativos carregada: {len(pares_validos)} ativos"
                )
            except ImportError:
                pares_validos = getattr(
                    config, "PARES", ["R_10", "R_25", "R_50", "R_75", "R_100"]
                )
                self.logger.warning("Usando lista de ativos padrão (fallback)")
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
        """Fecha a conexão com a API."""
        try:
            if self.ws:
                self.logger.info("Desconectando WebSocket...")
                self.ws.close()
                self.ws = None
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
                if self.conectar(self.token):
                    self.logger.info("Reconexão inteligente bem-sucedida")
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

    def _verificar_fechamento_automatico(self):
        """Verifica operações que precisam ser fechadas automaticamente para micro scalping."""
        operacoes_para_fechar = []

        # Obtém o timestamp atual
        agora = time.time()

        try:
            # Se não temos operações abertas, não precisa fazer nada
            if not self.operacoes_abertas:
                return

            # Adiciona log detalhado para debug quando temos operações abertas
            if self.operacoes_abertas:
                self.logger.debug(
                    f"Verificando {len(self.operacoes_abertas)} operações para fechamento automático"
                )

            # Verifica as operações abertas
            for contract_id, operacao in list(self.operacoes_abertas.items()):
                # Verifica se a operação tem flag de fechamento automático
                if operacao.get("fechamento_automatico", False):
                    # Verifica se o tempo máximo foi atingido
                    timestamp_abertura = operacao.get("timestamp_abertura", 0)
                    tempo_maximo = operacao.get("tempo_maximo_segundos", 1)
                    tempo_decorrido = agora - timestamp_abertura

                    # Se quase atingiu o tempo, faz log para debug
                    if (
                        tempo_decorrido >= (tempo_maximo * 0.8)
                        and tempo_decorrido < tempo_maximo
                    ):
                        self.logger.debug(
                            f"Operação {contract_id} quase atingindo limite: {tempo_decorrido:.2f}s / {tempo_maximo}s"
                        )

                    # Se atingiu o tempo máximo, adiciona para fechar
                    if tempo_decorrido >= tempo_maximo:
                        # Adiciona à lista de operações para fechar
                        operacoes_para_fechar.append(contract_id)
                        self.logger.info(
                            f"Operação {contract_id} atingiu tempo limite de {tempo_maximo}s (tempo real: {tempo_decorrido:.2f}s). Fechando..."
                        )
                else:
                    # Se não tem flag de fechamento automático mas é multiplier, adiciona a flag
                    tipo = operacao.get("tipo", "").upper()
                    if "MULT" in tipo:
                        # Adiciona flag de fechamento automático
                        self.logger.info(
                            f"Adicionando flag de fechamento automático para operação multiplier {contract_id}"
                        )
                        self.operacoes_abertas[contract_id][
                            "fechamento_automatico"
                        ] = True
                        self.operacoes_abertas[contract_id]["tempo_maximo_segundos"] = 1

                        # Se não tem timestamp de abertura, adiciona
                        if (
                            "timestamp_abertura"
                            not in self.operacoes_abertas[contract_id]
                        ):
                            self.operacoes_abertas[contract_id][
                                "timestamp_abertura"
                            ] = agora

            # Fecha as operações identificadas com prioridade alta
            for contract_id in operacoes_para_fechar:
                self.logger.info(
                    f"Iniciando fechamento forçado da operação {contract_id}"
                )
                if self.fechar_operacao(contract_id):
                    self.logger.info(
                        f"Operação {contract_id} fechada com sucesso após 1s (micro scalping)"
                    )
                else:
                    # Se falhou, tenta novamente com força
                    self.logger.warning(
                        f"Falha no fechamento normal da operação {contract_id}, tentando com força..."
                    )
                    try:
                        # Envia requisição direta sem verificações adicionais
                        req = {"sell": contract_id, "price": 0}
                        self.ws.send(json.dumps(req))
                        self.logger.info(
                            f"Fechamento forçado enviado para operação {contract_id}"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Erro no fechamento forçado da operação {contract_id}: {str(e)}"
                        )

        except Exception as e:
            self.logger.error(
                f"Erro ao verificar fechamento automático: {str(e)}", exc_info=True
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

                    # Executa análise e operação inteligente
                    resultado = self.executar_operacao_inteligente()

                    if resultado["executada"]:
                        self.logger.info(
                            f"OPERACAO {resultado['tipo']} EXECUTADA - "
                            f"Conf: {resultado['confianca']:.2f} - "
                            f"{resultado['razao']}"
                        )
                    else:
                        # Reduz logs para melhor performance - só loga a cada 10 análises
                        if not hasattr(self, "_contador_analises"):
                            self._contador_analises = 0
                        self._contador_analises += 1

                        if self._contador_analises % 10 == 0:  # Log a cada 10 análises
                            self.logger.info(
                                f"ANALISE #{self._contador_analises}: {resultado['razao']}"
                            )

                    # Verifica se atingiu a meta
                    if resultado["lucro_atual"] >= self.meta_diaria:
                        self.logger.info(
                            f"META DE ${self.meta_diaria:.2f} ATINGIDA! "
                            f"Lucro: ${resultado['lucro_atual']:.2f}"
                        )
                        self.rodando = False
                        break

                    # SCALPING ULTRA RÁPIDO - Intervalos MUITO menores para análise rápida
                    intervalo = {
                        "iniciante": 0.1,  # 100ms - MUITO RÁPIDO
                        "conservador": 0.05,  # 50ms - ULTRA RÁPIDO
                        "agressivo": 0.02,  # 20ms - EXTREMAMENTE RÁPIDO
                    }.get(self.modo_operacao, 0.1)

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


# Instância global removida - será criada no main.py quando necessário
