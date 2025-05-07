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

        # Novos atributos para micro scalping
        self.modo_operacao = "iniciante"  # iniciante, conservador ou agressivo
        self.meta_diaria = config.TAKE_PROFIT
        self.operacoes_ativas = 0
        self.operacoes_historico = []
        self.perdas_consecutivas = 0
        self.meta_minima = config.MICRO_SCALPING["meta_minima"]
        self.martingale_ativo = False
        self.ultimo_valor_entrada = 0

    def iniciar(
        self, token: str = None, modo: str = "iniciante", meta: float = None
    ) -> bool:
        try:
            self.logger.info(f"Iniciando aplicação de scalping no modo {modo}...")

            # Configura modo e meta
            self.modo_operacao = modo.lower()
            if meta is not None:
                self.meta_diaria = max(self.meta_minima, float(meta))

            # Reset de contadores
            self.operacoes_ativas = 0
            self.perdas_consecutivas = 0
            self.martingale_ativo = False
            self.operacoes_historico = []
            self.entradas_recentes = []

            # Tenta conectar o motor utilizando o token fornecido ou o configurado como padrão
            token_utilizado = token or config.ACTIVE_TOKEN
            if not token_utilizado:
                self.logger.error("Nenhum token Deriv informado para conexão.")
                return False

            # Conecta somente se ainda não houver uma conexão ativa ou se o token mudou
            if not self.motor.conectado or self.motor.token != token_utilizado:
                if not self.motor.conectar(token_utilizado):
                    self.logger.error(
                        "Falha ao conectar ao motor com o token informado"
                    )
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

        # Verifica se atingiu a meta
        if lucro_atual >= self.meta_diaria:
            self.logger.info("🎯 Meta diária atingida. Encerrando sessão.")
            self.parar()
            return

        # Verifica stop loss
        config_modo = getattr(config, f"MODO_{self.modo_operacao.upper()}")
        stop_loss_valor = self.meta_diaria * config_modo["stop_percent"]

        if lucro_atual <= -stop_loss_valor:
            self.logger.info(
                f"🛑 Stop Loss atingido ({lucro_atual:.2f}). Encerrando sessão."
            )
            self.parar()
            return

        # Verifica perdas consecutivas
        if self.perdas_consecutivas >= config_modo["stop_consecutivos"]:
            self.logger.info(
                f"🛑 Stop Loss por perdas consecutivas ({self.perdas_consecutivas}). Encerrando sessão."
            )
            self.parar()
            return

        # Executa a análise de micro scalping
        velas = self.catalogador.obter_velas()

        from inteligencia import analisar_micro_scalping

        analise = analisar_micro_scalping(
            velas=velas,
            meta=self.meta_diaria,
            lucro_atual=lucro_atual,
            modo=self.modo_operacao,
            operacoes_ativas=self.operacoes_ativas,
        )

        # Verifica se temos um sinal e se a confiança é suficiente
        if analise["sinal"] and analise["confianca"] >= 0.7:
            self.logger.info(
                f"Sinal detectado: {analise['sinal']} - {analise['razao']}"
            )
            tipo_operacao = "CALL" if analise["sinal"] == "compra" else "PUT"
            self._executar_operacao(tipo_operacao)

    def _executar_operacao(self, tipo_operacao: str):
        try:
            self.logger.info(f"Executando operação: {tipo_operacao}")

            self.operacao_em_andamento = True
            self.entradas_recentes.append(tipo_operacao)

            # Calcula valor da entrada com base no modo e meta
            config_modo = getattr(config, f"MODO_{self.modo_operacao.upper()}")
            valor_entrada = self.meta_diaria * config_modo["percent_entrada"]

            # Verifica se é martingale
            if self.martingale_ativo and self.perdas_consecutivas > 0:
                valor_entrada = self.ultimo_valor_entrada * 2
                self.logger.info(f"Aplicando martingale. Valor: {valor_entrada:.2f}")

            # Guarda o valor para possível martingale futuro
            self.ultimo_valor_entrada = valor_entrada

            # Certifica que o valor da entrada é adequado para a meta mínima
            if self.meta_diaria <= self.meta_minima:
                # Encontra um ativo que suporte entradas pequenas
                self.motor.par_atual = self._selecionar_ativo_valor_pequeno()

            # Incrementa contador de operações ativas
            self.operacoes_ativas += 1

            sucesso = self.motor.comprar(tipo_operacao, valor_entrada)

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

                # Atualiza lucro da sessão
                lucro_op = (
                    self.motor.obter_saldo() - self.saldo_inicial - self.lucro_sessao
                )
                self.lucro_sessao = self.motor.obter_saldo() - self.saldo_inicial

                # Registra resultado para controle de martingale e perdas consecutivas
                if lucro_op > 0:
                    self.perdas_consecutivas = 0
                    self.martingale_ativo = False
                else:
                    self.perdas_consecutivas += 1

                    # Ativa martingale se permitido para o modo
                    if self.perdas_consecutivas <= config_modo["martingale"]:
                        self.martingale_ativo = True
                    else:
                        self.martingale_ativo = False

                # Registra operação no histórico
                self.operacoes_historico.append(
                    {
                        "tipo": tipo_operacao,
                        "valor": valor_entrada,
                        "resultado": lucro_op,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                # Decrementa contador de operações ativas
                self.operacoes_ativas -= 1

                self.logger.info(
                    f"Operação concluída. Lucro/Perda: {lucro_op:.2f}, Lucro da sessão: {self.lucro_sessao:.2f}"
                )
            else:
                self.logger.error("Falha ao executar operação")
                # Decrementa contador em caso de falha
                self.operacoes_ativas -= 1

            self.operacao_em_andamento = False

        except Exception as e:
            self.logger.error(f"Erro ao executar operação: {e}")
            self.operacoes_ativas -= 1
            self.operacao_em_andamento = False

    def _selecionar_ativo_valor_pequeno(self) -> str:
        """Seleciona um ativo adequado para valores pequenos de entrada."""
        # Por padrão, os ativos volatility de índice mais baixo suportam valores menores
        return "R_10"  # Volatility 10 Index

    def parar(self):
        if not self.rodando:
            return
        self.logger.info("Parando aplicação de scalping...")
        self.rodando = False
        self.motor.rodando = False
        self.lucro_sessao = self.motor.obter_saldo() - self.saldo_inicial
        self.logger.info(f"Aplicação parada. Lucro da sessão: {self.lucro_sessao:.2f}")

    def status(self) -> Dict:
        """Retorna informações sobre o estado atual do robô."""
        tempo_execucao = (
            (datetime.now() - self.hora_inicio).total_seconds()
            if self.hora_inicio
            else 0
        )

        return {
            "rodando": self.rodando,
            "operacoes_realizadas": self.contador_operacoes,
            "operacoes_ativas": self.operacoes_ativas,
            "lucro_sessao": self.lucro_sessao,
            "saldo_atual": self.motor.obter_saldo(),
            "saldo_inicial": self.saldo_inicial,
            "tempo_execucao": tempo_execucao,
            "modo": self.modo_operacao,
            "meta_diaria": self.meta_diaria,
            "meta_progresso": (
                (self.lucro_sessao / self.meta_diaria * 100)
                if self.meta_diaria > 0
                else 0
            ),
            "perdas_consecutivas": self.perdas_consecutivas,
            "status_operacao": self._obter_status_operacao(),
            "ultimo_log": self._obter_ultimo_log(),
        }

    def _obter_status_operacao(self) -> Dict:
        """Retorna o status atual da operação para a interface."""
        if not self.rodando:
            return {"etapa": "parado", "progresso": 0}

        if self.operacao_em_andamento:
            return {"etapa": "abrindo", "progresso": 50}

        # Verifica se há operações ativas abertas
        if self.operacoes_ativas > 0:
            return {"etapa": "analisando", "progresso": 75}

        # Se tem resultados recentes (últimos 10 segundos)
        if (
            self.operacoes_historico
            and (
                datetime.now()
                - datetime.fromisoformat(self.operacoes_historico[-1]["timestamp"])
            ).total_seconds()
            < 10
        ):
            return {"etapa": "finalizado", "progresso": 100}

        # Estado padrão quando está rodando mas sem operações no momento
        return {"etapa": "analisando", "progresso": 25}

    def _obter_ultimo_log(self) -> str:
        """Retorna uma mensagem de log personalizada baseada no estado atual."""
        if not self.rodando:
            return "Robô parado. Aguardando inicialização."

        if self.operacao_em_andamento:
            tipo = (
                "CALL"
                if self.entradas_recentes and self.entradas_recentes[-1] == "CALL"
                else "PUT"
            )
            return f"Executando operação {tipo}. Aguardando resultado..."

        if self.operacoes_ativas > 0:
            return f"Operações ativas: {self.operacoes_ativas}. Monitorando mercado..."

        # Se tem operações no histórico, exibe resultado da última
        if self.operacoes_historico:
            ultima_op = self.operacoes_historico[-1]
            resultado = ultima_op["resultado"]
            tipo = ultima_op["tipo"]
            if resultado > 0:
                return f"✅ Última operação {tipo}: GANHO de ${resultado:.2f}"
            else:
                return f"❌ Última operação {tipo}: PERDA de ${abs(resultado):.2f}"

        config_modo = getattr(config, f"MODO_{self.modo_operacao.upper()}")
        return f"Analisando mercado no modo {self.modo_operacao.upper()} (Win rate estimado: {config_modo['win_rate']}%)"

    def obter_historico(self) -> List:
        """Retorna o histórico de operações."""
        return self.motor.historico_operacoes + self.operacoes_historico
