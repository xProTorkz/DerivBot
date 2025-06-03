# app.py - Controlador do sistema de scalping com melhorias gerais e controle de meta/stop

import os
import json
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from src import config
from src.core.motor import Motor
from src.core.catalogador import (
    Catalogador,
    analisar_entrada_chatgpt,
    analisar_saida_chatgpt,
)
from src.core.inteligencia import Inteligencia


class App:
    def __init__(self):
        """Inicializa a aplicação de scalping."""
        # Configuração de logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler("trading.log"), logging.StreamHandler()],
        )
        self.logger = logging.getLogger("app")

        # Motor de conexão com a Deriv
        self.motor = Motor()
        self.catalogador = self.motor.catalogador  # Referência direta ao catalogador

        # Estado da aplicação
        self.rodando = False
        self.operacao_em_andamento = False
        self.operacoes_ativas = 0  # contador para múltiplas operações

        # Estatísticas de operação
        self.hora_inicio = datetime.now()
        self.contador_operacoes = 0
        self.saldo_inicial = 0.0
        self.perdas_consecutivas = 0
        self.modo_operacao = "iniciante"
        self.meta_diaria = config.TAKE_PROFIT
        self.operacoes_historico = []
        self.entradas_recentes = []
        self.ultimo_lucro_conhecido = (
            0.0  # Armazena o último lucro conhecido quando o robô estava ativo
        )
        self._ultima_analise = {}  # Armazena a última análise do mercado

        # Limite de perdas e controle de modo
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
                self.meta_diaria = float(
                    meta
                )  # Usa exatamente o valor definido pelo usuário
            else:
                self.meta_diaria = (
                    config.TAKE_PROFIT
                )  # Usa valor padrão apenas se não houver meta definida

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
        # Sempre catalogar o tick, independentemente do estado do robô
        self.catalogador.adicionar_tick(preco)

        # Análise de mercado sempre em execução (mesmo que o robô não esteja ativo)
        velas = self.catalogador.obter_velas()

        # Importa aqui para evitar circular imports
        from src.core.inteligencia import (
            analisar_micro_scalping,
            detectar_suporte_resistencia,
        )

        # Detecta níveis de suporte e resistência para identificar melhores entradas
        suportes, resistencias = detectar_suporte_resistencia(velas, janela=5)
        preco_atual = velas[-1]["close"] if velas else preco

        # Verifica se estamos em um ponto de suporte ou resistência
        from src.core.inteligencia import esta_em_suporte, esta_em_resistencia

        em_suporte = esta_em_suporte(preco_atual, suportes)
        em_resistencia = esta_em_resistencia(preco_atual, resistencias)

        # Grava informações de análise mesmo sem o robô estar ativo
        lucro_atual = self.motor.obter_saldo() - self.saldo_inicial
        analise = analisar_micro_scalping(
            velas=velas,
            meta=self.meta_diaria,
            lucro_atual=lucro_atual,
            modo=self.modo_operacao,
            operacoes_ativas=self.operacoes_ativas,
        )

        # Guarda a análise e pontos de entrada ideais para consulta posterior
        self._ultima_analise = {
            "timestamp": datetime.now().isoformat(),
            "preco": preco_atual,
            "suportes": suportes,
            "resistencias": resistencias,
            "em_suporte": em_suporte,
            "em_resistencia": em_resistencia,
            "sinal": analise.get("sinal"),
            "confianca": analise.get("confianca", 0),
            "razao": analise.get("razao", ""),
        }

        # Registra no log pontos de entrada ideais (suporte/resistência)
        if em_suporte or em_resistencia:
            tipo_ponto = "suporte" if em_suporte else "resistência"
            self.logger.info(
                f"Ponto de {tipo_ponto} detectado! Preço: {preco_atual:.5f}"
            )

            # Se o sinal da IA também coincidir, destaca ainda mais no log
            if analise.get("sinal") and analise.get("confianca", 0) >= 0.7:
                self.logger.info(
                    f"🎯 OPORTUNIDADE IDEAL: Sinal {analise['sinal']} em ponto de {tipo_ponto}!"
                )

        # Se o robô não estiver ativo, apenas armazena a análise e não executa operações
        if not self.rodando:
            return

        # A partir daqui é o código original que só executa se o robô estiver ativo
        if self.operacao_em_andamento:
            return

        if self.contador_operacoes >= config.MAX_OPERATIONS:
            self.logger.info("Limite de operações atingido. Parando robô.")
            self.parar()
            return

        # NOVO: Verificador inteligente de meta e operações em aberto
        lucro_atual = self.motor.obter_saldo() - self.saldo_inicial
        meta_progresso_percent = (
            (lucro_atual / self.meta_diaria * 100) if self.meta_diaria > 0 else 0
        )

        # Verifica se a meta já foi atingida
        if lucro_atual >= self.meta_diaria:
            self.logger.info(
                f"🎯 Meta diária atingida ({lucro_atual:.2f} >= {self.meta_diaria:.2f}). Encerrando sessão."
            )
            self.parar()
            return

        # Verifica stop loss
        config_modo = getattr(config, f"MODO_{self.modo_operacao.upper()}")
        stop_loss_valor = self.meta_diaria * config_modo["stop_percent"]
        if lucro_atual <= -stop_loss_valor:
            self.logger.info(
                f"🛑 Stop Loss atingido ({lucro_atual:.2f} <= -{stop_loss_valor:.2f}). Encerrando sessão."
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

        # Lógica de redução/pausa de operações perto da meta
        pode_operar = True
        razao_pausa = ""
        max_operacoes_ajustado = config_modo["max_operacoes"]

        if self.operacoes_ativas > 0:
            # Calcula o lucro potencial das operações abertas (estimativa conservadora)
            # Nota: Para multipliers, o lucro real varia. Usamos uma estimativa.
            # Idealmente, o motor.py deveria fornecer o valor atual das posições abertas.
            # Assumindo um lucro mínimo pequeno ou zero para segurança ao se aproximar da meta.
            potencial_lucro_abertas = (
                0  # Estimativa conservadora para evitar ultrapassar a meta
            )
            # Se tivéssemos o valor atual das posições:
            # valor_atual_abertas = self.motor.obter_valor_atual_operacoes_abertas()
            # valor_compra_abertas = sum(op['valor'] for op in self.motor.operacoes_abertas.values())
            # potencial_lucro_abertas = valor_atual_abertas - valor_compra_abertas

            if (
                lucro_atual + potencial_lucro_abertas >= self.meta_diaria * 0.98
            ):  # Se já está muito perto ou pode atingir
                pode_operar = False
                razao_pausa = f"Meta próxima ({meta_progresso_percent:.1f}%). Lucro atual + potencial ({lucro_atual + potencial_lucro_abertas:.2f}) >= 98% da meta. Pausando novas entradas."
                self.logger.info(razao_pausa)

        # Reduz gradualmente o número de operações permitidas conforme se aproxima da meta
        if (
            pode_operar
            and meta_progresso_percent
            >= config.MICRO_SCALPING["meta_progresso_reducao"]
        ):
            fator_reducao = (100 - meta_progresso_percent) / (
                100 - config.MICRO_SCALPING["meta_progresso_reducao"]
            )
            max_operacoes_ajustado = max(
                1, int(config_modo["max_operacoes"] * fator_reducao)
            )
            self.logger.info(
                f"Próximo da meta ({meta_progresso_percent:.1f}%). Reduzindo max_operacoes para {max_operacoes_ajustado}."
            )

        # Verifica se o número atual de operações ativas excede o limite ajustado
        if self.operacoes_ativas >= max_operacoes_ajustado:
            pode_operar = False
            if not razao_pausa:  # Evita log duplicado
                razao_pausa = f"Limite ajustado de operações ({max_operacoes_ajustado}) atingido perto da meta. Aguardando fechamento."
                self.logger.info(razao_pausa)

        # Se não pode operar, retorna
        if not pode_operar:
            self._ultima_analise["sinal"] = (
                None  # Garante que não haja sinal se pausado
            )
            self._ultima_analise["razao"] = razao_pausa
            return

        # --- Fim do Verificador Inteligente de Meta ---

        # Verifica se temos um sinal e se a confiança é suficiente (considerando o modo)
        confianca_minima = config.IA_CONFIG["min_confianca"]
        if self.modo_operacao == "iniciante":
            # A confiança mínima para iniciante foi definida dentro da própria função de análise
            # Mas podemos adicionar uma camada extra aqui se necessário, ou confiar na lógica já implementada.
            pass  # A lógica de confiança já está mais rígida em analisar_micro_scalping

        if analise["sinal"] and analise["confianca"] >= confianca_minima:
            # Verifica novamente se pode operar antes de executar
            if self.operacoes_ativas < max_operacoes_ajustado:
                self.logger.info(
                    f"Sinal detectado: {analise['sinal']} (Conf: {analise['confianca']:.2f}) - {analise['razao']}"
                )
                tipo_operacao = "CALL" if analise["sinal"] == "compra" else "PUT"
                self._executar_operacao(tipo_operacao)
            else:
                self.logger.info(
                    f"Sinal detectado ({analise['sinal']}), mas limite de operações ({self.operacoes_ativas}/{max_operacoes_ajustado}) atingido. Aguardando."
                )

    def _executar_operacao(self, tipo_operacao: str):
        try:
            self.logger.info(f"Executando operação: {tipo_operacao}")

            self.operacao_em_andamento = True
            self.entradas_recentes.append(tipo_operacao)

            # Calcula valor da entrada com base no modo e meta
            config_modo = getattr(config, f"MODO_{self.modo_operacao.upper()}")
            valor_entrada = self.meta_diaria * config_modo["percent_entrada"]

            # Valores mínimos de entrada para os diferentes ativos da Deriv
            valores_minimos = {
                "R_10": 0.35,  # Volatility 10 Index
                "R_25": 0.35,  # Volatility 25 Index
                "R_50": 0.40,  # Volatility 50 Index
                "R_75": 0.45,  # Volatility 75 Index
                "R_100": 0.50,  # Volatility 100 Index
                "BOOM500": 0.50,  # Boom 500 Index
                "BOOM1000": 0.50,  # Boom 1000 Index
                "CRASH500": 0.50,  # Crash 500 Index
                "CRASH1000": 0.50,  # Crash 1000 Index
            }

            # Ativo preferencial para operações de micro scalping (1 segundo)
            ativo_selecionado = (
                "R_100"  # Alterado de R_10 para R_100 conforme solicitado
            )

            # Valor mínimo para o ativo selecionado
            valor_minimo = valores_minimos.get(ativo_selecionado, 0.35)

            # Garante que o valor de entrada seja pelo menos o mínimo aceito pelo ativo
            valor_entrada = max(valor_entrada, valor_minimo)

            self.logger.info(
                f"Valor calculado para entrada (micro scalping): ${valor_entrada:.2f} (mínimo: ${valor_minimo:.2f})"
            )

            # Verifica se é martingale
            if self.martingale_ativo and self.perdas_consecutivas > 0:
                valor_entrada = max(self.ultimo_valor_entrada * 2, valor_minimo)
                self.logger.info(f"Aplicando martingale. Valor: ${valor_entrada:.2f}")

            # Arredonda o valor para 2 casas decimais para evitar erros de precisão
            valor_entrada = round(valor_entrada, 2)

            # Guarda o valor para possível martingale futuro
            self.ultimo_valor_entrada = valor_entrada

            # Define o ativo atual no motor
            self.motor.definir_par(ativo_selecionado)
            self.logger.info(
                f"Par atual definido para: {ativo_selecionado} (micro scalping)"
            )

            # Registra o saldo antes da operação
            saldo_antes = self.motor.obter_saldo()

            # Incrementa contador de operações ativas
            self.operacoes_ativas += 1

            # Executa a operação com o valor calculado (modo multiplier para micro scalping)
            self.logger.info(
                f"Enviando ordem {tipo_operacao} de ${valor_entrada:.2f} em {ativo_selecionado} (modo multiplier/1s)"
            )

            # Verifica a quantidade de operações abertas antes de enviar a ordem
            operacoes_antes = len(self.motor.operacoes_abertas)

            # Usa o método comprar que já foi modificado para usar contratos multiplier
            sucesso = self.motor.comprar(tipo_operacao, valor_entrada)
            self.logger.info(f"Ordem de micro scalping enviada com sucesso: {sucesso}")

            if sucesso:
                self.contador_operacoes += 1

                # Aguarda a ordem ser processada (máximo 5 segundos)
                max_espera = 5  # segundos
                tempo_inicio = time.time()
                while time.time() - tempo_inicio < max_espera:
                    # Verifica se uma nova operação foi adicionada às operações abertas
                    if len(self.motor.operacoes_abertas) > operacoes_antes:
                        self.logger.info(
                            f"Operação de micro scalping aberta detectada!"
                        )
                        break
                    time.sleep(0.2)  # Pequena pausa

                # Aguarda apenas 1 segundo para micro scalping (+ margem de processamento)
                # O fechamento automático é feito pelo motor, mas aguardamos aqui também
                self.logger.info(
                    f"Aguardando 1.5 segundos para resultado de micro scalping..."
                )
                time.sleep(1.5)  # 1 segundo para a operação + margem

                # Aguarda mais um pouco para ter certeza que a operação foi processada
                for _ in range(10):  # Aguarda até 2 segundos adicionais
                    if len(self.motor.operacoes_abertas) <= operacoes_antes:
                        # A operação foi fechada, podemos prosseguir
                        break
                    time.sleep(0.2)

                # Verifica o saldo depois da operação
                saldo_depois = self.motor.obter_saldo()
                lucro_op = saldo_depois - saldo_antes  # Diferença real no saldo

                self.logger.info(
                    f"Resultado da operação de micro scalping: Saldo anterior: ${saldo_antes}, Saldo atual: ${saldo_depois}, Diferença: ${lucro_op}"
                )

                # O lucro da sessão agora é calculado corretamente com base nas operações reais
                self.lucro_sessao = self.motor.obter_saldo() - self.saldo_inicial

                # Força a atualização do saldo para garantir valor correto
                self.motor.saldo = saldo_depois

                # Registra resultado para controle de martingale e perdas consecutivas
                if lucro_op > 0:
                    self.perdas_consecutivas = 0
                    self.martingale_ativo = False
                    self.logger.info(
                        f"✅ GANHO na operação de micro scalping: +${lucro_op}"
                    )
                else:
                    self.perdas_consecutivas += 1
                    self.logger.info(
                        f"❌ PERDA na operação de micro scalping: ${lucro_op}"
                    )

                    # Ativa martingale se permitido para o modo
                    if self.perdas_consecutivas <= config_modo["martingale"]:
                        self.martingale_ativo = True
                    else:
                        self.martingale_ativo = False

                # Registra operação no histórico local (mesmo se já estiver no motor)
                nova_operacao = {
                    "tipo": tipo_operacao,
                    "valor": valor_entrada,
                    "resultado": lucro_op,
                    "timestamp": datetime.now().isoformat(),
                }
                self.operacoes_historico.append(nova_operacao)

                # Adiciona ao histórico do motor também para garantir consistência
                timestamp_agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.motor.historico_operacoes.append(
                    {
                        "id": f"manual_{int(time.time())}",
                        "preco_entrada": valor_entrada,
                        "preco_saida": valor_entrada + lucro_op,
                        "lucro": lucro_op,
                        "timestamp_abertura": timestamp_agora,
                        "timestamp_fechamento": timestamp_agora,
                        "tipo": tipo_operacao.upper(),
                    }
                )

                # Decrementa contador de operações ativas
                self.operacoes_ativas -= 1

                self.logger.info(
                    f"Operação de micro scalping concluída. Lucro/Perda: {lucro_op:.2f}, Lucro da sessão: {self.lucro_sessao:.2f}"
                )
            else:
                self.logger.error("Falha ao executar operação de micro scalping")
                # Decrementa contador em caso de falha
                self.operacoes_ativas -= 1

            self.operacao_em_andamento = False

        except Exception as e:
            self.logger.error(f"Erro ao executar operação de micro scalping: {e}")
            self.operacoes_ativas -= 1
            self.operacao_em_andamento = False

    def _selecionar_ativo_valor_pequeno(self) -> str:
        """Seleciona um ativo adequado para valores pequenos de entrada."""
        # Verificamos a lista de ativos válidos do config.py
        # Os ativos com índice mais baixo geralmente aceitam valores menores
        # R_10 é o que aceita menores valores de entrada e tem alta volatilidade
        return "R_10"  # Volatility 10 Index - Aceita entradas a partir de 0.35

    def parar(self):
        """Para a execução do robô."""
        if self.rodando:
            self.logger.info("Parando robô...")

            # Armazena o último lucro conhecido antes de parar
            self.ultimo_lucro_conhecido = self.motor.obter_saldo() - self.saldo_inicial

            self.motor.rodando = False
            self.rodando = False
            self.logger.info("Robô parado com sucesso.")
            return True
        return False

    def status(self) -> Dict:
        """Retorna o status atual da aplicação."""
        tempo_execucao = (
            (datetime.now() - self.hora_inicio).total_seconds() if self.rodando else 0
        )

        saldo_atual = self.motor.obter_saldo()

        # Calcula o lucro baseado no estado do robô
        if self.rodando:
            lucro_sessao = saldo_atual - self.saldo_inicial
            # Atualiza o último lucro conhecido
            self.ultimo_lucro_conhecido = lucro_sessao
        else:
            # Usa o último lucro conhecido quando o robô não está rodando
            lucro_sessao = self.ultimo_lucro_conhecido

        # Calcula porcentagem de progresso em relação à meta
        meta_progresso = (
            (lucro_sessao / self.meta_diaria * 100) if self.meta_diaria > 0 else 0
        )
        meta_progresso = max(0, min(100, meta_progresso))  # Limita entre 0-100%

        # Obtém o status detalhado da operação atual
        status_operacao = self._obter_status_operacao()

        return {
            "rodando": self.rodando,
            "tempo_execucao": tempo_execucao,
            "operacoes_realizadas": self.contador_operacoes,
            "operacoes_ativas": self.operacoes_ativas,
            "saldo_atual": saldo_atual,
            "saldo_inicial": self.saldo_inicial,
            "lucro_sessao": lucro_sessao,
            "meta_diaria": self.meta_diaria,
            "meta_progresso": meta_progresso,
            "modo": self.modo_operacao,
            "perdas_consecutivas": self.perdas_consecutivas,
            "ultimo_log": self._obter_ultimo_log(),
            "status_operacao": status_operacao,
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
                - datetime.fromisoformat(self.operacoes_historico[-1].get("timestamp"))
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

    def obter_ultima_analise(self) -> Dict:
        """
        Retorna a última análise realizada, mesmo sem o robô estar ativo.
        Esta função permite verificar na interface os pontos de entrada ideais.
        """
        padrao = {
            "timestamp": None,
            "preco": 0,
            "suportes": [],
            "resistencias": [],
            "em_suporte": False,
            "em_resistencia": False,
            "sinal": None,
            "confianca": 0,
            "razao": "Sem análise disponível",
        }
        if not hasattr(self, "_ultima_analise") or not self._ultima_analise:
            return padrao
        # Garante que todos os campos existem e não são null
        resultado = padrao.copy()
        resultado.update(
            {k: v for k, v in self._ultima_analise.items() if v is not None}
        )
        return resultado
