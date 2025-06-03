"""
Módulo de gerenciamento de estado da API
Responsável por manter o estado da aplicação e fornecer endpoints para o frontend
"""

import json
import logging
import time
import random
from datetime import datetime

# Configuração de logging
logger = logging.getLogger("DerivBot.EstadoAPI")

class EstadoAPI:
    def __init__(self):
        """
        Inicializa a API de estado
        """
        self.robo_ativo = False
        self.modo_operacao = "iniciante"
        self.meta_diaria = 50.0
        self.lucro_atual = 0.0
        self.saldo_atual = 0.0
        self.operacoes = 0
        self.status_operacao = "parado"
        self.mensagem = "Robô pronto para iniciar"
        self.historico = []
        self.ultima_atualizacao = time.time()
    
    def iniciar_robo(self, modo="iniciante", meta=50.0):
        """
        Inicia o robô
        
        Args:
            modo: Modo de operação (iniciante, conservador, agressivo)
            meta: Meta diária em dólares
            
        Returns:
            dict: Status da operação
        """
        self.robo_ativo = True
        self.modo_operacao = modo
        self.meta_diaria = float(meta)
        self.status_operacao = "analisando"
        self.mensagem = f"Robô iniciado no modo {modo.upper()} com meta de ${meta:.2f}"
        self.ultima_atualizacao = time.time()
        
        logger.info(f"Robô iniciado: modo={modo}, meta=${meta:.2f}")
        
        return {
            "status": "iniciado",
            "modo": self.modo_operacao,
            "meta": self.meta_diaria,
            "mensagem": self.mensagem
        }
    
    def parar_robo(self):
        """
        Para o robô
        
        Returns:
            dict: Status da operação
        """
        self.robo_ativo = False
        self.status_operacao = "parado"
        self.mensagem = "Robô parado pelo usuário"
        self.ultima_atualizacao = time.time()
        
        logger.info("Robô parado pelo usuário")
        
        return {
            "status": "parado",
            "mensagem": self.mensagem
        }
    
    def obter_status(self):
        """
        Obtém o status atual do robô
        
        Returns:
            dict: Status atual do robô
        """
        # Se o robô estiver ativo, simula atualizações de status
        if self.robo_ativo:
            self._simular_atualizacao_status()
        
        return {
            "ativo": self.robo_ativo,
            "modo": self.modo_operacao,
            "meta": self.meta_diaria,
            "lucro": self.lucro_atual,
            "saldo": self.saldo_atual,
            "operacoes": self.operacoes,
            "status_operacao": self.status_operacao,
            "mensagem_log": self.mensagem
        }
    
    def obter_status_detalhado(self):
        """
        Obtém o status detalhado do robô
        
        Returns:
            dict: Status detalhado do robô
        """
        # Se o robô estiver ativo, simula atualizações de status
        if self.robo_ativo:
            self._simular_atualizacao_status()
        
        return {
            "ativo": self.robo_ativo,
            "modo": self.modo_operacao,
            "meta": self.meta_diaria,
            "lucro": self.lucro_atual,
            "saldo": self.saldo_atual,
            "operacoes": self.operacoes,
            "status_operacao": self.status_operacao,
            "mensagem_log": self.mensagem,
            "historico_recente": self.historico[-5:] if self.historico else []
        }
    
    def adicionar_operacao(self, tipo, valor, resultado):
        """
        Adiciona uma operação ao histórico
        
        Args:
            tipo: Tipo da operação (CALL/PUT)
            valor: Valor da entrada
            resultado: Resultado da operação (lucro/prejuízo)
            
        Returns:
            dict: Operação adicionada
        """
        agora = datetime.now()
        operacao = {
            "data": agora.strftime("%d/%m/%Y"),
            "hora": agora.strftime("%H:%M:%S"),
            "timestamp": agora.timestamp(),
            "tipo": tipo,
            "valor": valor,
            "resultado_real": resultado
        }
        
        self.historico.append(operacao)
        self.operacoes += 1
        self.lucro_atual += resultado
        self.ultima_atualizacao = time.time()
        
        return operacao
    
    def limpar_historico(self):
        """
        Limpa o histórico de operações
        
        Returns:
            dict: Status da operação
        """
        self.historico = []
        self.operacoes = 0
        self.lucro_atual = 0.0
        self.ultima_atualizacao = time.time()
        
        return {
            "status": "ok",
            "mensagem": "Histórico limpo com sucesso"
        }
    
    def _simular_atualizacao_status(self):
        """
        Simula atualizações de status para demonstração
        """
        # Só atualiza a cada 3 segundos
        if time.time() - self.ultima_atualizacao < 3:
            return
        
        # Atualiza o timestamp
        self.ultima_atualizacao = time.time()
        
        # Ciclo de estados para demonstração
        estados = ["analisando", "medio", "abrindo", "aguardando", "finalizado"]
        mensagens = [
            "Analisando mercado em busca do melhor momento...",
            "Sinal identificado, preparando entrada...",
            "Abrindo contrato agora!",
            "Contrato aberto, aguardando resultado...",
            "Operação finalizada com GANHO! +$8.50"
        ]
        
        # Determina o próximo estado
        if self.status_operacao == "parado":
            self.status_operacao = "analisando"
            self.mensagem = mensagens[0]
        elif self.status_operacao == "analisando":
            self.status_operacao = "medio"
            self.mensagem = mensagens[1]
        elif self.status_operacao == "medio":
            self.status_operacao = "abrindo"
            self.mensagem = mensagens[2]
        elif self.status_operacao == "abrindo":
            self.status_operacao = "aguardando"
            self.mensagem = mensagens[3]
        elif self.status_operacao == "aguardando":
            # Decide se é win ou loss
            if random.random() > 0.3:
                self.status_operacao = "finalizado-win"
                resultado = random.uniform(5, 10)
                self.mensagem = f"Operação finalizada com GANHO! +${resultado:.2f}"
                self.adicionar_operacao("CALL" if random.random() > 0.5 else "PUT", 10, resultado)
            else:
                self.status_operacao = "finalizado-loss"
                resultado = random.uniform(5, 10) * -1
                self.mensagem = f"Operação finalizada com perda. -${abs(resultado):.2f}"
                self.adicionar_operacao("CALL" if random.random() > 0.5 else "PUT", 10, resultado)
        else:
            # Volta para analisando
            self.status_operacao = "analisando"
            self.mensagem = mensagens[0]
