"""
Módulo de gerenciamento de API para o DerivBot
Responsável por comunicação com a API da Deriv
"""

import json
import logging
import websocket
import threading
import time
import random
from datetime import datetime

# Configuração de logging
logger = logging.getLogger("DerivBot.Motor")


class DerivAPI:
    def __init__(self, token):
        """
        Inicializa a API da Deriv

        Args:
            token: Token de autenticação da Deriv
        """
        self.token = token
        self.ws = None
        self.conectado = False
        self.saldo = 0.0
        self.conta_id = ""
        self.conta_nome = ""
        self.conta_tipo = ""
        self.thread_ws = None
        self.callbacks = {}
        self.request_id = 1
        self.respostas = {}  # Para armazenar respostas das requisições

        # Tenta conectar ao inicializar
        self.conectar()

    def conectar(self):
        """
        Conecta à API da Deriv

        Returns:
            bool: True se conectou com sucesso, False caso contrário
        """
        try:
            # Fecha conexão anterior se existir
            if self.ws:
                self.ws.close()

            # Inicializa nova conexão
            self.ws = websocket.WebSocketApp(
                "wss://ws.binaryws.com/websockets/v3?app_id=71203",
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )

            # Inicia thread para o websocket
            self.thread_ws = threading.Thread(target=self.ws.run_forever)
            self.thread_ws.daemon = True
            self.thread_ws.start()

            # Aguarda conexão
            timeout = 5
            start_time = time.time()
            while not self.conectado and time.time() - start_time < timeout:
                time.sleep(0.1)

            return self.conectado

        except Exception as e:
            logger.error(f"Erro ao conectar à API: {e}")
            return False

    def _on_open(self, ws):
        """
        Callback quando a conexão é aberta

        Args:
            ws: WebSocket
        """
        logger.info("Conexão com a API estabelecida")
        self.conectado = True

        # Autoriza com o token
        self._enviar_mensagem({"authorize": self.token})

    def _on_message(self, ws, message):
        """
        Callback quando uma mensagem é recebida

        Args:
            ws: WebSocket
            message: Mensagem recebida
        """
        try:
            dados = json.loads(message)

            # Processa autorização
            if "authorize" in dados and dados["authorize"]:
                self.conta_id = dados["authorize"]["loginid"]
                self.conta_nome = dados["authorize"].get("fullname", "")
                self.saldo = float(dados["authorize"]["balance"])
                # Determina tipo de conta: CR = real, VRTC = demo
                self.conta_tipo = "real" if self.conta_id.startswith("CR") else "demo"
                logger.info(f"Autorizado como {self.conta_id} ({self.conta_tipo})")

            # Processa saldo
            if "balance" in dados and dados["balance"]:
                self.saldo = float(dados["balance"]["balance"])
                logger.debug(f"Saldo atualizado: {self.saldo}")

            # Processa callbacks
            req_id = dados.get("req_id")
            if req_id:
                # Armazena resposta para consulta posterior
                self.respostas[req_id] = dados

                # Executa callback se existir
                if req_id in self.callbacks:
                    callback = self.callbacks[req_id]
                    callback(dados)
                    del self.callbacks[req_id]

        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}")

    def _on_error(self, ws, error):
        """
        Callback quando ocorre um erro

        Args:
            ws: WebSocket
            error: Erro ocorrido
        """
        logger.error(f"Erro na conexão WebSocket: {error}")
        self.conectado = False

    def _on_close(self, ws, close_status_code, close_msg):
        """
        Callback quando a conexão é fechada

        Args:
            ws: WebSocket
            close_status_code: Código de status de fechamento
            close_msg: Mensagem de fechamento
        """
        logger.info("Conexão com a API fechada")
        self.conectado = False

    def _enviar_mensagem(self, mensagem, callback=None):
        """
        Envia uma mensagem para a API

        Args:
            mensagem: Mensagem a ser enviada
            callback: Função de callback para a resposta

        Returns:
            int: ID da requisição
        """
        if not self.conectado:
            if not self.conectar():
                logger.error("Não foi possível conectar à API")
                return -1

        try:
            # Adiciona ID da requisição
            req_id = self.request_id
            self.request_id += 1
            mensagem["req_id"] = req_id

            # Registra callback se fornecido
            if callback:
                self.callbacks[req_id] = callback

            # Envia mensagem
            self.ws.send(json.dumps(mensagem))
            return req_id

        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
            return -1

    def verificar_token(self):
        """
        Verifica se o token é válido

        Returns:
            dict: Resultado da verificação
        """
        # Simula verificação de token (em uma implementação real, usaria a API)
        # Nesta versão simplificada, consideramos o token válido se tiver pelo menos 5 caracteres
        if len(self.token) < 5:
            return {"status": "erro", "mensagem": "Token inválido"}

        # Determina o tipo de conta baseado no token
        # Se o token contém "demo" ou "VRTC", é uma conta demo
        # Caso contrário, é uma conta real
        is_demo = "demo" in self.token.lower() or "vrtc" in self.token.lower()

        # Simula dados da conta de forma mais determinística
        if is_demo:
            self.conta_id = f"VRTC{random.randint(10000, 99999)}"
            self.conta_tipo = "demo"
            # Saldo demo mais alto e consistente
            self.saldo = round(random.uniform(10000, 50000), 2)
        else:
            self.conta_id = f"CR{random.randint(10000, 99999)}"
            self.conta_tipo = "real"
            # Saldo real mais baixo mas realista
            self.saldo = round(random.uniform(100, 1000), 2)

        self.conta_nome = "Usuário Teste"

        return {
            "status": "ok",
            "conta_id": self.conta_id,
            "conta_nome": self.conta_nome,
            "conta_tipo": self.conta_tipo,
            "saldo": self.saldo,
        }

    def verificar_conexao(self):
        """
        Verifica se a conexão está ativa

        Returns:
            dict: Status da conexão
        """
        if not self.conectado:
            return {"status": "erro", "mensagem": "Não conectado à API"}

        return {
            "status": "ok",
            "conta_id": self.conta_id,
            "conta_nome": self.conta_nome,
            "conta_tipo": self.conta_tipo,
            "saldo": self.saldo,
        }

    def obter_saldo(self):
        """
        Obtém o saldo atual

        Returns:
            dict: Saldo atual
        """
        try:
            if not self.conectado:
                return {"status": "erro", "mensagem": "Não conectado à API"}

            # Envia requisição para obter saldo usando o método existente
            req_id = self._enviar_mensagem({"balance": 1})

            if req_id == -1:
                return {"status": "erro", "mensagem": "Erro ao enviar requisição"}

            # Aguarda resposta por até 5 segundos
            import time

            timeout = time.time() + 5
            while time.time() < timeout:
                if req_id in self.respostas:
                    resposta = self.respostas.pop(req_id)

                    if "balance" in resposta:
                        self.saldo = float(resposta["balance"]["balance"])
                        return {"status": "ok", "saldo": self.saldo}
                    elif "error" in resposta:
                        return {
                            "status": "erro",
                            "mensagem": resposta["error"]["message"],
                        }

                time.sleep(0.1)

            # Se não recebeu resposta, usa saldo atual se disponível
            if self.saldo > 0:
                return {"status": "ok", "saldo": self.saldo}

            # Se não tem saldo, tenta fazer uma nova requisição de autorização para obter saldo atualizado
            if hasattr(self, "conta_id") and self.conta_id:
                # Faz nova requisição de autorização para obter saldo real
                auth_req_id = self._enviar_mensagem({"authorize": self.token})

                if auth_req_id != -1:
                    # Aguarda resposta da autorização por 3 segundos
                    auth_timeout = time.time() + 3
                    while time.time() < auth_timeout:
                        if auth_req_id in self.respostas:
                            auth_resposta = self.respostas.pop(auth_req_id)

                            if (
                                "authorize" in auth_resposta
                                and auth_resposta["authorize"]
                            ):
                                self.saldo = float(
                                    auth_resposta["authorize"]["balance"]
                                )
                                return {"status": "ok", "saldo": self.saldo}

                        time.sleep(0.1)

            return {"status": "erro", "mensagem": "Não foi possível obter saldo real"}

        except Exception as e:
            logger.error(f"Erro ao obter saldo: {e}")
            return {"status": "erro", "mensagem": str(e)}

    def abrir_contrato(self, tipo, valor):
        """
        Abre um contrato

        Args:
            tipo: Tipo do contrato (CALL/PUT)
            valor: Valor da entrada

        Returns:
            dict: Resultado da abertura do contrato
        """
        # Simula abertura de contrato (em uma implementação real, usaria a API)
        contrato_id = f"C{random.randint(1000000, 9999999)}"

        return {
            "status": "ok",
            "contrato_id": contrato_id,
            "tipo": tipo,
            "valor": valor,
            "timestamp": datetime.now().timestamp(),
        }

    def verificar_resultado(self, contrato_id):
        """
        Verifica o resultado de um contrato

        Args:
            contrato_id: ID do contrato

        Returns:
            dict: Resultado do contrato
        """
        # Simula verificação de resultado (em uma implementação real, usaria a API)
        # Nesta versão simplificada, geramos um resultado aleatório
        win = random.random() > 0.3
        valor_entrada = random.uniform(1, 10)

        if win:
            resultado = valor_entrada * 0.8  # Lucro de 80%
        else:
            resultado = -valor_entrada  # Perda total

        return {
            "status": "ok",
            "contrato_id": contrato_id,
            "resultado": resultado,
            "win": win,
            "timestamp": datetime.now().timestamp(),
        }

    def fechar(self):
        """
        Fecha a conexão com a API
        """
        if self.ws:
            self.ws.close()
        self.conectado = False
