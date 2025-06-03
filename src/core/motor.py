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


class Motor:
    def __init__(self):
        """Inicializa o motor de operações."""
        self.ws = None
        self.conectado = False
        self.token = None
        self.saldo = 0.0
        self.operacoes_abertas = {}
        self.historico_operacoes = []
        self.callback_tick = None
        self.ultima_resposta = None
        self.ultima_cotacao = None
        self.par_atual = getattr(config, "PAR_PADRAO", "R_100")
        self.scanner_ativo = True  # Ativa o scanner de ativos
        self.ultimo_scan_ativo = 0  # Timestamp do último scan
        self.modo_real = getattr(config, "MODO_REAL", True)
        self.catalogador = Catalogador()
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

        # Logger específico
        self.logger = logging.getLogger("motor")

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

    def conectar(self, token):
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
        self.logger.error(f"Erro na conexão WebSocket: {str(error)}")
        self.ultimo_erro = f"Erro de conexão: {str(error)}"

        # Agenda reconexão
        self._agendar_reconexao()

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

            # Muda o ativo se necessário
            if melhor_ativo and melhor_ativo != self.par_atual:
                # Log mais limpo para o usuário
                self.logger.info(f"Mudando para {melhor_ativo} (melhor oportunidade)")
                self.definir_par(melhor_ativo)

        except Exception as e:
            self.logger.error(f"Erro no scanner de ativos: {e}")

    # FUNÇÃO REMOVIDA - Usar catalogador.obter_ativo_recomendado() diretamente

    def registrar_callback_tick(self, callback: Callable[[float], None]):
        """Registra um callback para ser chamado a cada tick recebido."""
        self.callback_tick = callback

    def executar_operacao_inteligente(self, cliente_id: str = "default") -> dict:
        """Executa operação usando o sistema inteligente baseado no modo atual."""
        try:
            # Calcula lucro atual
            lucro_atual = self.obter_saldo() - self.saldo_inicial

            # Conta operações ativas
            self.operacoes_ativas_count = len(self.operacoes_abertas)

            # Usa o catalogador para análise inteligente
            analise = self.catalogador.analisar_scalping(
                cliente_id=cliente_id,
                modo=self.modo_operacao,
                meta=self.meta_diaria,
                lucro_atual=lucro_atual,
                operacoes_ativas=self.operacoes_ativas_count,
            )

            # Se não há sinal, retorna a análise
            if not analise["sinal"]:
                return {
                    "executada": False,
                    "razao": analise["razao"],
                    "confianca": analise["confianca"],
                    "lucro_atual": lucro_atual,
                    "operacoes_ativas": self.operacoes_ativas_count,
                }

            # Se há sinal, executa a operação
            tipo_operacao = "CALL" if analise["sinal"] == "compra" else "PUT"
            valor_entrada = analise["valor_entrada"]

            # Executa a operação
            sucesso = self.comprar(tipo_operacao, valor_entrada)

            if sucesso:
                self.logger.info(
                    f"Operação {tipo_operacao} executada - Valor: ${valor_entrada:.2f} - "
                    f"Confiança: {analise['confianca']:.2f} - Razão: {analise['razao']}"
                )

                return {
                    "executada": True,
                    "tipo": tipo_operacao,
                    "valor": valor_entrada,
                    "confianca": analise["confianca"],
                    "razao": analise["razao"],
                    "lucro_esperado": analise["lucro_esperado"],
                    "lucro_atual": lucro_atual,
                    "operacoes_ativas": self.operacoes_ativas_count + 1,
                }
            else:
                return {
                    "executada": False,
                    "razao": "Falha ao executar operação na API",
                    "confianca": analise["confianca"],
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
        """Envia ordem de compra para a API usando contratos multipliers para micro scalping."""
        try:
            with self.lock:
                if not self.ws or not self.conectado:
                    self.logger.error("Não conectado à API. Tentando reconectar...")
                    self._tentar_reconectar()
                    return False

                # Verifica se o valor está acima do mínimo permitido para o ativo
                if valor < 0.35:  # Valor mínimo para R_10
                    self.logger.error(
                        f"Valor da ordem (${valor:.2f}) abaixo do mínimo permitido (${0.35})"
                    )
                    return False

                # Para multipliers, usamos CALL = UP e PUT = DOWN
                contract_type = (
                    "MULTUP" if tipo.lower() in ["compra", "call"] else "MULTDOWN"
                )

                # Multiplier padrão para micro scalping (1x = menor risco possível)
                multiplier = 1

                # Registra o timestamp de início da operação
                timestamp_inicio = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Prepara o request com ID de transação para rastreabilidade
                transaction_id = f"tx_{int(time.time())}"

                # Configura requisição para contrato multiplier
                req = {
                    "buy": 1,
                    "parameters": {
                        "contract_type": contract_type,
                        "symbol": self.par_atual,
                        "amount": valor,
                        "basis": "stake",
                        "multiplier": multiplier,  # Parâmetro específico para contratos multipliers
                    },
                    "price": valor,
                    "passthrough": {"transaction_id": transaction_id},
                }

                self.logger.info(
                    f"Enviando ordem {contract_type} (x{multiplier}) de ${valor:.2f} para {self.par_atual} (ID: {transaction_id})"
                )
                self.ws.send(json.dumps(req))

                # Armazena informações da transação pendente
                if not hasattr(self, "transacoes_pendentes"):
                    self.transacoes_pendentes = {}

                self.transacoes_pendentes[transaction_id] = {
                    "tipo": contract_type,
                    "valor": valor,
                    "multiplier": multiplier,
                    "timestamp": timestamp_inicio,
                    "par": self.par_atual,
                    "processada": False,
                    "fechamento_automatico": True,  # Indica que deve ser fechado automaticamente
                    "tempo_maximo_segundos": 1,  # Tempo máximo que a operação deve ficar aberta (1 segundo)
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

                # Inscreve no novo
                return self._inscrever_ticks()
            else:
                # Apenas atualiza o par, inscrição será feita quando conectar
                self.par_atual = par
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
        """Agenda uma tentativa de reconexão."""
        if not self.reconectado_recentemente:
            thread = threading.Thread(target=self._tentar_reconectar)
            thread.daemon = True
            thread.start()

    def _tentar_reconectar(self):
        """Tenta reconectar ao WebSocket com estratégia de backoff exponencial."""
        if self.reconectado_recentemente:
            return

        self.reconectado_recentemente = True
        max_tentativas = self.max_tentativas_reconexao

        for tentativa in range(1, max_tentativas + 1):
            self.logger.info(f"Tentativa de reconexão {tentativa}/{max_tentativas}...")

            # Aumenta o intervalo a cada tentativa (exponential backoff)
            espera = self.intervalo_tentativas * (2 ** (tentativa - 1))

            # Tenta conectar
            if self.conectar(self.token):
                self.logger.info("Reconexão bem-sucedida!")
                return True

            # Aguarda antes da próxima tentativa
            time.sleep(min(espera, 30))  # Máximo de 30 segundos

        self.logger.error(f"Falha em reconectar após {max_tentativas} tentativas.")
        self.reconectado_recentemente = False
        return False

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
                        self._tentar_reconectar()

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

            # Marca como rodando
            self.rodando = True

            # Loop principal - continua enquanto o robô estiver ativo
            while self.rodando and hasattr(self, "conectado"):
                try:
                    if not self.conectado:
                        self.logger.warning(
                            "Motor desconectado, tentando reconectar..."
                        )
                        self._tentar_reconectar()
                        time.sleep(5)
                        continue

                    # Executa análise e operação inteligente
                    resultado = self.executar_operacao_inteligente()

                    if resultado["executada"]:
                        self.logger.info(
                            f"✅ {resultado['tipo']} executada - "
                            f"Conf: {resultado['confianca']:.2f} - "
                            f"{resultado['razao']}"
                        )
                    else:
                        self.logger.debug(f"📊 {resultado['razao']}")

                    # Verifica se atingiu a meta
                    if resultado["lucro_atual"] >= self.meta_diaria:
                        self.logger.info(
                            f"🎯 Meta de ${self.meta_diaria:.2f} atingida! "
                            f"Lucro: ${resultado['lucro_atual']:.2f}"
                        )
                        self.rodando = False
                        break

                    # Log de debug para acompanhar o funcionamento
                    self.logger.debug(
                        f"Sistema inteligente rodando - Lucro: ${resultado['lucro_atual']:.2f} / Meta: ${self.meta_diaria:.2f}"
                    )

                    # SCALPING ULTRA RÁPIDO - Intervalos muito menores
                    intervalo = {
                        "iniciante": 1,
                        "conservador": 0.5,
                        "agressivo": 0.2,
                    }.get(self.modo_operacao, 1)

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
