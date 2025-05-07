# app.py - Controlador do sistema de scalping com melhorias gerais e controle de meta/stop

import time
import logging
from typing import Dict, List, Union
from datetime import datetime

import config
from motor import Motor
from catalogador import Catalogador, analisar_entrada_chatgpt, analisar_saida_chatgpt


class App:
    def __init__(self):
        logging.basicConfig(
            level=getattr(logging, config.LOG_LEVEL),
            format="%(asctime)s - %(levelname)s - %(message)s",
            filename=config.LOG_FILE,
        )
        self.logger = logging.getLogger("ScalpingApp")

        self.motor = Motor()
        self.catalogador = Catalogador()

        self.rodando = False
        self.operacao_em_andamento = False
        self.ultima_operacao = None
        self.contador_operacoes = 0
        self.saldo_inicial = 0
        self.lucro_sessao = 0
        self.hora_inicio = None
        self.entradas_recentes = []

    def iniciar(self) -> bool:
        try:
            self.logger.info("Iniciando aplicação de scalping...")

            if not self.motor.conectar():
                self.logger.error("Falha ao conectar ao motor")
                return False

            self.motor.registrar_callback_tick(self._processar_tick)
            self.motor.rodando = True

            self.saldo_inicial = self.motor.obter_saldo()
            self.logger.info(f"Saldo inicial: {self.saldo_inicial}")

            self.rodando = True
            self.hora_inicio = datetime.now()
            self.logger.info(f"Aplicação iniciada em {self.hora_inicio}")

            return True

        except Exception as e:
            self.logger.error(f"Erro ao iniciar aplicação: {e}")
            return False

    def _processar_tick(self, preco: float):
        self.catalogador.adicionar_tick(preco)

        if self.operacao_em_andamento or not self.rodando:
            return

        if self.contador_operacoes >= config.MAX_OPERATIONS:
            self.logger.info("Limite de operações atingido. Parando robô.")
            self.parar()
            return

        # Verifica stop loss ou take profit
        lucro_atual = self.motor.obter_saldo() - self.saldo_inicial
        if lucro_atual >= config.TAKE_PROFIT:
            self.logger.info("🎯 Meta diária atingida. Encerrando sessão.")
            self.parar()
            return
        elif lucro_atual <= -config.STOP_LOSS:
            self.logger.info("🛑 Stop Loss atingido. Encerrando sessão.")
            self.parar()
            return

        velas = self.catalogador.obter_velas()
        sinal = analisar_entrada_chatgpt(velas, lucro_atual, self.entradas_recentes)

        if sinal in ["CALL", "PUT"]:
            self._executar_operacao(sinal)

    def _executar_operacao(self, tipo_operacao: str):
        try:
            self.logger.info(f"Executando operação: {tipo_operacao}")

            self.operacao_em_andamento = True
            self.entradas_recentes.append(tipo_operacao)

            sucesso = self.motor.comprar(tipo_operacao, config.VALOR_ENTRADA)

            if sucesso:
                self.contador_operacoes += 1
                self.logger.info(
                    f"Operação {self.contador_operacoes} iniciada com sucesso"
                )

                # Aguarda o timeframe
                time.sleep(config.TIMEFRAME)

                # Verifica saída
                velas = self.catalogador.obter_velas()
                lucro_atual = self.motor.obter_saldo() - self.saldo_inicial
                decisao_saida = analisar_saida_chatgpt(velas, lucro_atual)

                if decisao_saida == "SAIR":
                    self.motor.fechar_operacao()

                self.lucro_sessao = self.motor.obter_saldo() - self.saldo_inicial
                self.logger.info(
                    f"Operação concluída. Lucro da sessão: {self.lucro_sessao}"
                )
            else:
                self.logger.error("Falha ao executar operação")

            self.operacao_em_andamento = False

        except Exception as e:
            self.logger.error(f"Erro ao executar operação: {e}")
            self.operacao_em_andamento = False

    def status(self) -> Dict:
        return {
            "rodando": self.rodando,
            "operacoes_realizadas": self.contador_operacoes,
            "operacao_em_andamento": self.operacao_em_andamento,
            "lucro_sessao": self.motor.obter_saldo() - self.saldo_inicial,
            "saldo_atual": self.motor.obter_saldo(),
            "par_atual": self.motor.par_atual,
            "modo": "REAL" if config.MODO_REAL else "DEMO",
            "tempo_execucao": (
                str(datetime.now() - self.hora_inicio)
                if self.hora_inicio
                else "00:00:00"
            ),
        }

    def parar(self) -> bool:
        try:
            self.logger.info("Parando aplicação...")
            self.rodando = False
            self.motor.rodando = False
            self.motor.desconectar()
            self.catalogador.limpar_dados()
            self.logger.info(
                f"Aplicação encerrada. Lucro da sessão: {self.lucro_sessao}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Erro ao parar aplicação: {e}")
            return False

    def trocar_par(self, par: str) -> bool:
        self.catalogador.limpar_dados()
        return self.motor.definir_par(par)

    def obter_historico(self) -> List[Dict]:
        return self.motor.obter_historico()
