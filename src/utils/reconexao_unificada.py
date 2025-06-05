#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sistema de Reconexão Unificado para DerivBot
Gerencia todas as reconexões do sistema de forma robusta e inteligente
"""

import time
import threading
import websocket
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timedelta
from src.utils.logger_unificado import logger_unificado


class ReconexaoUnificada:
    """Sistema unificado de reconexão para todas as conexões do DerivBot"""
    
    def __init__(self):
        # Configurações de reconexão
        self.max_tentativas = 5
        self.delay_inicial = 2  # segundos
        self.delay_maximo = 30  # segundos
        self.multiplicador_delay = 1.5
        
        # Estado das conexões
        self.conexoes_ativas = {}
        self.tentativas_reconexao = {}
        self.ultima_tentativa = {}
        self.callbacks_reconexao = {}
        
        # Thread de monitoramento
        self.thread_monitor = None
        self.monitoramento_ativo = False
        self._lock = threading.Lock()
        
        # Estatísticas
        self.total_reconexoes = 0
        self.reconexoes_bem_sucedidas = 0
        self.ultima_reconexao = None
        
        logger_unificado.info("Sistema de reconexão unificado inicializado", "conexao")
    
    def registrar_conexao(self, nome: str, funcao_conectar: Callable, 
                         funcao_verificar: Callable, callback_reconexao: Optional[Callable] = None) -> None:
        """
        Registra uma conexão para monitoramento
        
        Args:
            nome: Nome identificador da conexão
            funcao_conectar: Função para estabelecer conexão
            funcao_verificar: Função para verificar se conexão está ativa
            callback_reconexao: Função chamada após reconexão bem-sucedida
        """
        with self._lock:
            self.conexoes_ativas[nome] = {
                "funcao_conectar": funcao_conectar,
                "funcao_verificar": funcao_verificar,
                "callback_reconexao": callback_reconexao,
                "conectado": False,
                "ultima_verificacao": datetime.now(),
                "tentativas_falha": 0
            }
            
            self.tentativas_reconexao[nome] = 0
            self.ultima_tentativa[nome] = None
            
        logger_unificado.info(f"Conexão '{nome}' registrada para monitoramento", "conexao")
        
        # Inicia monitoramento se não estiver ativo
        if not self.monitoramento_ativo:
            self.iniciar_monitoramento()
    
    def remover_conexao(self, nome: str) -> None:
        """Remove uma conexão do monitoramento"""
        with self._lock:
            if nome in self.conexoes_ativas:
                del self.conexoes_ativas[nome]
                del self.tentativas_reconexao[nome]
                del self.ultima_tentativa[nome]
                
        logger_unificado.info(f"Conexão '{nome}' removida do monitoramento", "conexao")
    
    def iniciar_monitoramento(self) -> None:
        """Inicia o thread de monitoramento das conexões"""
        if self.monitoramento_ativo:
            return
        
        self.monitoramento_ativo = True
        self.thread_monitor = threading.Thread(target=self._monitorar_conexoes, daemon=True)
        self.thread_monitor.start()
        
        logger_unificado.info("Monitoramento de conexões iniciado", "conexao")
    
    def parar_monitoramento(self) -> None:
        """Para o monitoramento das conexões"""
        self.monitoramento_ativo = False
        if self.thread_monitor and self.thread_monitor.is_alive():
            self.thread_monitor.join(timeout=5)
        
        logger_unificado.info("Monitoramento de conexões parado", "conexao")
    
    def _monitorar_conexoes(self) -> None:
        """Thread principal de monitoramento"""
        while self.monitoramento_ativo:
            try:
                with self._lock:
                    conexoes_para_verificar = list(self.conexoes_ativas.items())
                
                for nome, info in conexoes_para_verificar:
                    self._verificar_conexao(nome, info)
                
                # Aguarda antes da próxima verificação
                time.sleep(5)
                
            except Exception as e:
                logger_unificado.error(f"Erro no monitoramento de conexões: {e}", "conexao")
                time.sleep(10)  # Aguarda mais tempo em caso de erro
    
    def _verificar_conexao(self, nome: str, info: Dict[str, Any]) -> None:
        """Verifica uma conexão específica"""
        try:
            # Verifica se a conexão está ativa
            conectado = info["funcao_verificar"]()
            
            with self._lock:
                info["ultima_verificacao"] = datetime.now()
                
                if conectado:
                    if not info["conectado"]:
                        # Conexão foi restaurada
                        logger_unificado.success(f"Conexão '{nome}' restaurada", "conexao", True)
                        info["conectado"] = True
                        info["tentativas_falha"] = 0
                        self.tentativas_reconexao[nome] = 0
                        
                        # Chama callback se disponível
                        if info["callback_reconexao"]:
                            try:
                                info["callback_reconexao"]()
                            except Exception as e:
                                logger_unificado.error(f"Erro no callback de reconexão '{nome}': {e}", "conexao")
                    
                    info["conectado"] = True
                else:
                    if info["conectado"]:
                        # Conexão foi perdida
                        logger_unificado.warning(f"Conexão '{nome}' perdida", "conexao", True)
                        info["conectado"] = False
                    
                    info["tentativas_falha"] += 1
                    
                    # Tenta reconectar se necessário
                    if self._deve_tentar_reconexao(nome):
                        self._tentar_reconexao(nome, info)
                        
        except Exception as e:
            logger_unificado.error(f"Erro ao verificar conexão '{nome}': {e}", "conexao")
            with self._lock:
                info["conectado"] = False
                info["tentativas_falha"] += 1
    
    def _deve_tentar_reconexao(self, nome: str) -> bool:
        """Verifica se deve tentar reconectar"""
        with self._lock:
            tentativas = self.tentativas_reconexao[nome]
            ultima_tentativa = self.ultima_tentativa[nome]
            
            # Verifica limite de tentativas
            if tentativas >= self.max_tentativas:
                return False
            
            # Verifica delay entre tentativas
            if ultima_tentativa:
                delay_necessario = min(
                    self.delay_inicial * (self.multiplicador_delay ** tentativas),
                    self.delay_maximo
                )
                
                if (datetime.now() - ultima_tentativa).total_seconds() < delay_necessario:
                    return False
            
            return True
    
    def _tentar_reconexao(self, nome: str, info: Dict[str, Any]) -> None:
        """Tenta reconectar uma conexão"""
        with self._lock:
            self.tentativas_reconexao[nome] += 1
            self.ultima_tentativa[nome] = datetime.now()
            tentativa_atual = self.tentativas_reconexao[nome]
        
        logger_unificado.warning(
            f"Tentando reconectar '{nome}' (tentativa {tentativa_atual}/{self.max_tentativas})", 
            "conexao", True
        )
        
        try:
            # Tenta reconectar
            sucesso = info["funcao_conectar"]()
            
            if sucesso:
                with self._lock:
                    info["conectado"] = True
                    info["tentativas_falha"] = 0
                    self.tentativas_reconexao[nome] = 0
                    self.total_reconexoes += 1
                    self.reconexoes_bem_sucedidas += 1
                    self.ultima_reconexao = datetime.now()
                
                logger_unificado.success(f"Reconexão '{nome}' bem-sucedida", "conexao", True)
                
                # Chama callback se disponível
                if info["callback_reconexao"]:
                    try:
                        info["callback_reconexao"]()
                    except Exception as e:
                        logger_unificado.error(f"Erro no callback de reconexão '{nome}': {e}", "conexao")
            else:
                logger_unificado.warning(f"Falha na reconexão '{nome}'", "conexao")
                
        except Exception as e:
            logger_unificado.error(f"Erro ao tentar reconectar '{nome}': {e}", "conexao")
            with self._lock:
                self.total_reconexoes += 1
    
    def forcar_reconexao(self, nome: str) -> bool:
        """Força uma tentativa de reconexão imediata"""
        with self._lock:
            if nome not in self.conexoes_ativas:
                logger_unificado.error(f"Conexão '{nome}' não encontrada", "conexao")
                return False
            
            info = self.conexoes_ativas[nome]
            # Reset das tentativas para permitir reconexão forçada
            self.tentativas_reconexao[nome] = 0
            self.ultima_tentativa[nome] = None
        
        logger_unificado.info(f"Forçando reconexão de '{nome}'", "conexao", True)
        self._tentar_reconexao(nome, info)
        
        # Verifica se a reconexão foi bem-sucedida
        time.sleep(2)
        return info["funcao_verificar"]()
    
    def obter_status_conexoes(self) -> Dict[str, Any]:
        """Obtém status de todas as conexões"""
        with self._lock:
            status = {}
            
            for nome, info in self.conexoes_ativas.items():
                status[nome] = {
                    "conectado": info["conectado"],
                    "ultima_verificacao": info["ultima_verificacao"].isoformat(),
                    "tentativas_falha": info["tentativas_falha"],
                    "tentativas_reconexao": self.tentativas_reconexao[nome],
                    "ultima_tentativa": (
                        self.ultima_tentativa[nome].isoformat() 
                        if self.ultima_tentativa[nome] else None
                    )
                }
            
            return {
                "conexoes": status,
                "estatisticas": {
                    "total_reconexoes": self.total_reconexoes,
                    "reconexoes_bem_sucedidas": self.reconexoes_bem_sucedidas,
                    "taxa_sucesso": (
                        self.reconexoes_bem_sucedidas / self.total_reconexoes * 100
                        if self.total_reconexoes > 0 else 0
                    ),
                    "ultima_reconexao": (
                        self.ultima_reconexao.isoformat() 
                        if self.ultima_reconexao else None
                    )
                }
            }
    
    def resetar_estatisticas(self) -> None:
        """Reseta as estatísticas de reconexão"""
        with self._lock:
            self.total_reconexoes = 0
            self.reconexoes_bem_sucedidas = 0
            self.ultima_reconexao = None
            
            # Reset das tentativas de todas as conexões
            for nome in self.tentativas_reconexao:
                self.tentativas_reconexao[nome] = 0
                self.ultima_tentativa[nome] = None
        
        logger_unificado.info("Estatísticas de reconexão resetadas", "conexao")


# Instância global do sistema de reconexão
reconexao_unificada = ReconexaoUnificada()
