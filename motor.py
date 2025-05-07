# motor.py - Atualizado para integração total com painel, meta e catalogador

import time
import json
import websocket
import threading
import config
from datetime import datetime
from typing import Dict, List, Optional, Union, Callable

from catalogador import Catalogador  # Integração com o sistema de análise


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
        self.par_atual = config.PAR_PADRAO
        self.modo_real = config.MODO_REAL
        self.catalogador = Catalogador()
        self.rodando = False
        self.meta_atingida = False
        self.saldo_inicial = 0.0
        self.lock = threading.Lock()

        # Armazena último erro de autenticação/conexão recebido da Deriv
        self.ultimo_erro = None

    def conectar(self, token):
        self.token = token
        # Cloudflare 530/1016 indica que ws.deriv.com não resolve em algumas regiões.
        # Domínio oficial conforme documentação: ws.derivws.com
        ws_url = "wss://ws.derivws.com/websockets/v3?app_id=71203"
        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        # Roda o WebSocket em uma thread separada
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()
        # Aguarda autenticação (máximo 10s)
        for _ in range(20):
            if self.conectado:
                return True
            time.sleep(0.5)
        return False

    def _on_open(self, ws):
        # Envia o token para autenticar
        req = {"authorize": self.token}
        ws.send(json.dumps(req))

    def _on_message(self, ws, message):
        print("Mensagem recebida:", message)
        try:
            data = json.loads(message)
            self.ultima_resposta = data

            if "authorize" in data and data["authorize"]:
                self.conectado = True
                self.saldo = data["authorize"].get("balance", 0)
                self.saldo_inicial = self.saldo
                print(f"Autenticado com sucesso. Saldo: {self.saldo}")
                self._inscrever_ticks()

            if "tick" in data and data["tick"]:
                tick_data = data["tick"]
                self.ultima_cotacao = tick_data.get("quote", 0)
                self.catalogador.adicionar_tick(self.ultima_cotacao)

                if self.callback_tick:
                    self.callback_tick(self.ultima_cotacao)

                if not self.rodando or self.meta_atingida:
                    return

                # Modificado para usar análise de micro scalping
                from inteligencia import analisar_micro_scalping

                velas = self.catalogador.obter_velas()
                lucro_atual = self.obter_saldo() - self.saldo_inicial

                # Verificar se temos velas suficientes para análise
                if len(velas) >= 20:
                    analise = analisar_micro_scalping(
                        velas=velas,
                        meta=config.TAKE_PROFIT,
                        lucro_atual=lucro_atual,
                        modo="iniciante",  # Valor default, será sobrescrito pelo App
                    )

                    if analise["sinal"] and analise["confianca"] >= 0.8:
                        tipo_operacao = (
                            "CALL" if analise["sinal"] == "compra" else "PUT"
                        )
                        self.executar_operacao(tipo_operacao)

            if "buy" in data and data["buy"]:
                contract_id = data["buy"]["contract_id"]
                self.operacoes_abertas[contract_id] = {
                    "id": contract_id,
                    "preco_entrada": data["buy"]["buy_price"],
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "tipo": data["echo_req"]
                    .get("parameters", {})
                    .get("contract_type", ""),
                }
                print(f"Operação {contract_id} aberta com sucesso.")

            if "proposal_open_contract" in data and data["proposal_open_contract"]:
                contract = data["proposal_open_contract"]
                contract_id = contract["contract_id"]

                if contract["is_sold"] == 1 and contract_id in self.operacoes_abertas:
                    lucro = contract["profit"]
                    preco_entrada = self.operacoes_abertas[contract_id]["preco_entrada"]

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

                    self.historico_operacoes.append(resultado)
                    del self.operacoes_abertas[contract_id]

                    print(f"Operação {contract_id} fechada. Lucro: {lucro}")

                    lucro_total = self.obter_saldo() - self.saldo_inicial
                    if lucro_total >= config.TAKE_PROFIT:
                        print("🎯 Meta diária atingida!")
                        self.meta_atingida = True
                        self.rodando = False

            # Captura erros retornados pela API
            if "error" in data:
                self.ultimo_erro = data["error"].get("message", "Erro desconhecido")
                print(f"[DERIV ERROR] {self.ultimo_erro}")
                # Mantém conectado False para sinalizar falha
                self.conectado = False

        except Exception as e:
            print(f"Erro ao processar mensagem: {e}")

    def _on_error(self, ws, error):
        print(f"Erro na conexão: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        self.conectado = False
        print("Conexão fechada")

    def _autenticar(self):
        if not self.ws:
            return
        req = {"authorize": self.token}
        self.ws.send(json.dumps(req))

    def _inscrever_ticks(self):
        if not self.ws:
            return
        req = {"ticks": self.par_atual, "subscribe": 1}
        self.ws.send(json.dumps(req))

    def registrar_callback_tick(self, callback: Callable[[float], None]):
        self.callback_tick = callback

    def executar_operacao(self, tipo: str):
        sucesso = self.comprar(tipo, config.VALOR_ENTRADA)
        if sucesso:
            print(f"🔁 Operação {tipo.upper()} executada!")

    def comprar(self, tipo: str, valor: float) -> bool:
        if not self.ws or not self.conectado:
            print("Não conectado à API")
            return False

        contract_type = "CALL" if tipo.lower() == "compra" else "PUT"

        req = {
            "buy": 1,
            "parameters": {
                "amount": valor,
                "basis": "stake",
                "contract_type": contract_type,
                "currency": "USD",
                "duration": config.TIMEFRAME,
                "duration_unit": "s",
                "symbol": self.par_atual,
            },
            "price": valor,
        }

        try:
            self.ws.send(json.dumps(req))
            return True
        except Exception as e:
            print(f"Erro ao executar operação: {e}")
            return False

    def obter_saldo(self):
        return self.saldo if self.conectado else 0.0

    def definir_par(self, par: str) -> bool:
        if par not in config.PARES:
            print(f"Par {par} não suportado")
            return False

        self.par_atual = par
        if self.conectado:
            self._inscrever_ticks()
        return True

    def obter_historico(self) -> List[Dict]:
        return self.historico_operacoes

    def desconectar(self):
        if self.ws:
            self.ws.close()
        self.conectado = False
