#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sistema de Logs Unificado para DerivBot
Centraliza todos os logs do sistema para evitar duplicações e melhorar organização
"""

import logging
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
from collections import deque
import threading

# Importa configurações
try:
    from src.config.config import Config

    LOG_CONFIG = Config.LOG_CONFIG_AVANCADO
    VALIDACAO_CONFIG = Config.VALIDACAO
except ImportError:
    # Fallback se não conseguir importar
    LOG_CONFIG = {
        "nivel_console": "INFO",
        "nivel_arquivo": "DEBUG",
        "max_logs_memoria": 200,
        "max_logs_painel": 50,
        "categorias": {
            "sistema": {"cor": "#2196F3", "emoji": "⚙️"},
            "trading": {"cor": "#4CAF50", "emoji": "💹"},
            "stops": {"cor": "#FF9800", "emoji": "🛑"},
            "erro": {"cor": "#F44336", "emoji": "❌"},
            "sucesso": {"cor": "#4CAF50", "emoji": "✅"},
            "alerta": {"cor": "#FF5722", "emoji": "⚠️"},
        },
        "formato_timestamp": "%d/%m/%Y %H:%M:%S",
        "incluir_milissegundos": True,
        "auto_limpeza": True,
        "intervalo_limpeza": 3600,
    }
    VALIDACAO_CONFIG = {"max_erros_consecutivos": 3}


class LoggerUnificado:
    """Sistema de logs unificado para todo o DerivBot"""

    def __init__(self, max_logs_memoria=None, max_logs_painel=None):
        # Usa configurações centralizadas
        self.max_logs_memoria = max_logs_memoria or LOG_CONFIG.get(
            "max_logs_memoria", 200
        )
        self.max_logs_painel = max_logs_painel or LOG_CONFIG.get("max_logs_painel", 50)

        # Filas thread-safe para logs
        self._logs_tempo_real = deque(maxlen=self.max_logs_memoria)
        self._logs_painel = deque(maxlen=self.max_logs_painel)
        self._logs_sistema = deque(maxlen=self.max_logs_memoria)
        self._logs_stops = deque(maxlen=100)  # Logs específicos de stops
        self._logs_erros = deque(maxlen=100)  # Logs específicos de erros

        # Lock para thread safety
        self._lock = threading.Lock()

        # Configuração do logger principal
        self.logger = self._configurar_logger()

        # Contadores e estatísticas
        self._contador_logs = 0
        self._contador_erros_consecutivos = 0
        self._ultimo_erro_timestamp = 0
        self._ultima_limpeza = time.time()

        # Configurações de categorias
        self.categorias = LOG_CONFIG.get("categorias", {})

        # Auto-limpeza se habilitada
        if LOG_CONFIG.get("auto_limpeza", True):
            self._iniciar_auto_limpeza()

    def _configurar_logger(self) -> logging.Logger:
        """Configura o logger principal do sistema"""
        logger = logging.getLogger("DerivBot.Unificado")
        logger.setLevel(logging.INFO)

        # Remove handlers existentes para evitar duplicação
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Formatter unificado
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Handler para arquivo
        try:
            logs_dir = getattr(Config, "LOGS_DIR", "logs")
            os.makedirs(logs_dir, exist_ok=True)
            file_handler = logging.FileHandler(
                os.path.join(logs_dir, "derivbot_unificado.log"), encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Erro ao configurar log de arquivo: {e}")

        # Handler para console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger

    def _iniciar_auto_limpeza(self):
        """Inicia thread de auto-limpeza de logs antigos"""

        def auto_limpeza():
            while True:
                try:
                    time.sleep(LOG_CONFIG.get("intervalo_limpeza", 3600))
                    self._executar_limpeza_automatica()
                except Exception as e:
                    print(f"Erro na auto-limpeza de logs: {e}")

        thread = threading.Thread(target=auto_limpeza, daemon=True)
        thread.start()

    def _executar_limpeza_automatica(self):
        """Executa limpeza automática de logs antigos"""
        with self._lock:
            agora = time.time()
            if agora - self._ultima_limpeza > LOG_CONFIG.get("intervalo_limpeza", 3600):
                # Mantém apenas logs recentes
                self._logs_tempo_real = deque(
                    list(self._logs_tempo_real)[-self.max_logs_memoria // 2 :],
                    maxlen=self.max_logs_memoria,
                )
                self._logs_painel = deque(
                    list(self._logs_painel)[-self.max_logs_painel // 2 :],
                    maxlen=self.max_logs_painel,
                )
                self._ultima_limpeza = agora
                self.info("Auto-limpeza de logs executada", "sistema")

    def log(
        self,
        mensagem: str,
        nivel: str = "info",
        categoria: str = "sistema",
        incluir_painel: bool = False,
        incluir_tempo_real: bool = True,
    ) -> None:
        """
        Log unificado com categorização

        Args:
            mensagem: Mensagem do log
            nivel: Nível do log (info, warning, error, success)
            categoria: Categoria do log (sistema, trading, conexao, etc.)
            incluir_painel: Se deve aparecer no painel visual
            incluir_tempo_real: Se deve aparecer nos logs de tempo real
        """
        with self._lock:
            timestamp = datetime.now()
            timestamp_str = timestamp.strftime("%H:%M:%S")

            # Incrementa contador
            self._contador_logs += 1

            # Cria entrada de log
            log_entry = {
                "id": self._contador_logs,
                "timestamp": timestamp_str,
                "timestamp_full": timestamp.isoformat(),
                "mensagem": str(mensagem),
                "nivel": nivel,
                "categoria": categoria,
            }

            # Adiciona aos logs do sistema
            self._logs_sistema.append(log_entry)

            # Adiciona aos logs de tempo real se solicitado
            if incluir_tempo_real:
                self._logs_tempo_real.append(log_entry)

            # Adiciona aos logs do painel se solicitado
            if incluir_painel:
                self._logs_painel.append(log_entry)

            # Log no sistema de logging padrão
            nivel_logging = getattr(logging, nivel.upper(), logging.INFO)
            self.logger.log(nivel_logging, f"[{categoria.upper()}] {mensagem}")

    def info(
        self, mensagem: str, categoria: str = "sistema", incluir_painel: bool = False
    ) -> None:
        """Log de informação"""
        self.log(mensagem, "info", categoria, incluir_painel, True)

    def warning(
        self, mensagem: str, categoria: str = "sistema", incluir_painel: bool = True
    ) -> None:
        """Log de aviso"""
        self.log(mensagem, "warning", categoria, incluir_painel, True)

    def error(
        self, mensagem: str, categoria: str = "sistema", incluir_painel: bool = True
    ) -> None:
        """Log de erro"""
        self.log(mensagem, "error", categoria, incluir_painel, True)

    def success(
        self, mensagem: str, categoria: str = "trading", incluir_painel: bool = True
    ) -> None:
        """Log de sucesso"""
        self.log(mensagem, "success", categoria, incluir_painel, True)

    def trading(
        self, mensagem: str, nivel: str = "info", incluir_painel: bool = True
    ) -> None:
        """Log específico para trading"""
        self.log(mensagem, nivel, "trading", incluir_painel, True)

    def conexao(
        self, mensagem: str, nivel: str = "info", incluir_painel: bool = False
    ) -> None:
        """Log específico para conexão"""
        self.log(mensagem, nivel, "conexao", incluir_painel, True)

    def motor(
        self, mensagem: str, nivel: str = "info", incluir_painel: bool = False
    ) -> None:
        """Log específico para motor"""
        self.log(mensagem, nivel, "motor", incluir_painel, True)

    def catalogador(
        self, mensagem: str, nivel: str = "info", incluir_painel: bool = False
    ) -> None:
        """Log específico para catalogador"""
        self.log(mensagem, nivel, "catalogador", incluir_painel, True)

    def stops(
        self, mensagem: str, nivel: str = "warning", incluir_painel: bool = True
    ) -> None:
        """Log específico para sistema de stops"""
        with self._lock:
            # Adiciona emoji específico para stops
            emoji = self.categorias.get("stops", {}).get("emoji", "🛑")
            mensagem_formatada = f"{emoji} {mensagem}"

            # Log normal
            self.log(mensagem_formatada, nivel, "stops", incluir_painel, True)

            # Adiciona também aos logs específicos de stops
            log_entry = {
                "id": self._contador_logs,
                "timestamp": datetime.now().strftime(
                    LOG_CONFIG.get("formato_timestamp", "%H:%M:%S")
                ),
                "timestamp_full": datetime.now().isoformat(),
                "mensagem": mensagem_formatada,
                "nivel": nivel,
                "categoria": "stops",
            }
            self._logs_stops.append(log_entry)

    def erro_critico(
        self, mensagem: str, erro: Exception = None, incluir_painel: bool = True
    ) -> None:
        """Log para erros críticos com tratamento especial"""
        with self._lock:
            self._contador_erros_consecutivos += 1
            self._ultimo_erro_timestamp = time.time()

            # Formata mensagem de erro
            if erro:
                mensagem_completa = (
                    f"❌ ERRO CRÍTICO: {mensagem} | Detalhes: {str(erro)}"
                )
            else:
                mensagem_completa = f"❌ ERRO CRÍTICO: {mensagem}"

            # Log normal
            self.log(mensagem_completa, "error", "erro", incluir_painel, True)

            # Adiciona aos logs específicos de erros
            log_entry = {
                "id": self._contador_logs,
                "timestamp": datetime.now().strftime(
                    LOG_CONFIG.get("formato_timestamp", "%H:%M:%S")
                ),
                "timestamp_full": datetime.now().isoformat(),
                "mensagem": mensagem_completa,
                "nivel": "error",
                "categoria": "erro",
                "erro_consecutivo": self._contador_erros_consecutivos,
                "detalhes_erro": str(erro) if erro else None,
            }
            self._logs_erros.append(log_entry)

            # Verifica se atingiu limite de erros consecutivos
            max_erros = VALIDACAO_CONFIG.get("max_erros_consecutivos", 3)
            if self._contador_erros_consecutivos >= max_erros:
                self.log(
                    f"⚠️ ALERTA: {max_erros} erros consecutivos detectados! Sistema pode precisar de intervenção.",
                    "warning",
                    "sistema",
                    True,
                    True,
                )

    def sucesso_operacao(self, mensagem: str, incluir_painel: bool = True) -> None:
        """Log para sucessos em operações (reseta contador de erros)"""
        with self._lock:
            # Reseta contador de erros consecutivos em caso de sucesso
            if self._contador_erros_consecutivos > 0:
                self._contador_erros_consecutivos = 0
                self.log(
                    "✅ Contador de erros resetado após sucesso",
                    "info",
                    "sistema",
                    False,
                    False,
                )

            # Log de sucesso
            emoji = self.categorias.get("sucesso", {}).get("emoji", "✅")
            self.log(f"{emoji} {mensagem}", "success", "trading", incluir_painel, True)

    def obter_logs_tempo_real(self, limite: int = 20) -> List[Dict]:
        """Obtém logs de tempo real"""
        with self._lock:
            return list(self._logs_tempo_real)[-limite:]

    def obter_logs_painel(self, limite: int = 10) -> List[Dict]:
        """Obtém logs do painel"""
        with self._lock:
            return list(self._logs_painel)[-limite:]

    def obter_logs_sistema(self, limite: int = 50) -> List[Dict]:
        """Obtém logs do sistema"""
        with self._lock:
            return list(self._logs_sistema)[-limite:]

    def obter_logs_por_categoria(self, categoria: str, limite: int = 20) -> List[Dict]:
        """Obtém logs por categoria"""
        with self._lock:
            logs_categoria = [
                log for log in self._logs_sistema if log.get("categoria") == categoria
            ]
            return logs_categoria[-limite:]

    def obter_logs_stops(self, limite: int = 20) -> List[Dict]:
        """Obtém logs específicos de stops"""
        with self._lock:
            return list(self._logs_stops)[-limite:]

    def obter_logs_erros(self, limite: int = 20) -> List[Dict]:
        """Obtém logs específicos de erros"""
        with self._lock:
            return list(self._logs_erros)[-limite:]

    def obter_status_erros(self) -> Dict[str, Any]:
        """Obtém status atual dos erros"""
        with self._lock:
            return {
                "erros_consecutivos": self._contador_erros_consecutivos,
                "ultimo_erro_timestamp": self._ultimo_erro_timestamp,
                "tempo_desde_ultimo_erro": (
                    time.time() - self._ultimo_erro_timestamp
                    if self._ultimo_erro_timestamp > 0
                    else 0
                ),
                "total_erros": len(self._logs_erros),
                "limite_erros": VALIDACAO_CONFIG.get("max_erros_consecutivos", 3),
                "status": (
                    "critico"
                    if self._contador_erros_consecutivos
                    >= VALIDACAO_CONFIG.get("max_erros_consecutivos", 3)
                    else "normal"
                ),
            }

    def limpar_logs(self, categoria: Optional[str] = None) -> None:
        """Limpa logs (todos ou por categoria)"""
        with self._lock:
            if categoria:
                # Remove logs de categoria específica
                self._logs_sistema = deque(
                    [
                        log
                        for log in self._logs_sistema
                        if log.get("categoria") != categoria
                    ],
                    maxlen=self.max_logs_memoria,
                )

                self._logs_tempo_real = deque(
                    [
                        log
                        for log in self._logs_tempo_real
                        if log.get("categoria") != categoria
                    ],
                    maxlen=self.max_logs_memoria,
                )

                self._logs_painel = deque(
                    [
                        log
                        for log in self._logs_painel
                        if log.get("categoria") != categoria
                    ],
                    maxlen=self.max_logs_painel,
                )
            else:
                # Limpa todos os logs
                self._logs_sistema.clear()
                self._logs_tempo_real.clear()
                self._logs_painel.clear()
                self._contador_logs = 0

    def salvar_logs_arquivo(self, arquivo: str = None) -> bool:
        """Salva logs em arquivo JSON"""
        try:
            if not arquivo:
                arquivo = (
                    f"logs/logs_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )

            os.makedirs(os.path.dirname(arquivo), exist_ok=True)

            with self._lock:
                dados = {
                    "timestamp_backup": datetime.now().isoformat(),
                    "total_logs": len(self._logs_sistema),
                    "logs": list(self._logs_sistema),
                }

            with open(arquivo, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=2, ensure_ascii=False)

            self.info(f"Logs salvos em: {arquivo}", "sistema")
            return True

        except Exception as e:
            self.error(f"Erro ao salvar logs: {e}", "sistema")
            return False

    def obter_estatisticas(self) -> Dict[str, Any]:
        """Obtém estatísticas dos logs"""
        with self._lock:
            categorias = {}
            niveis = {}

            for log in self._logs_sistema:
                categoria = log.get("categoria", "desconhecido")
                nivel = log.get("nivel", "info")

                categorias[categoria] = categorias.get(categoria, 0) + 1
                niveis[nivel] = niveis.get(nivel, 0) + 1

            return {
                "total_logs": len(self._logs_sistema),
                "logs_tempo_real": len(self._logs_tempo_real),
                "logs_painel": len(self._logs_painel),
                "categorias": categorias,
                "niveis": niveis,
                "ultimo_log": (
                    list(self._logs_sistema)[-1] if self._logs_sistema else None
                ),
            }


# Instância global do logger unificado
logger_unificado = LoggerUnificado()


# Funções de conveniência para uso direto
def log_info(
    mensagem: str, categoria: str = "sistema", incluir_painel: bool = False
) -> None:
    """Função de conveniência para log info"""
    logger_unificado.info(mensagem, categoria, incluir_painel)


def log_warning(
    mensagem: str, categoria: str = "sistema", incluir_painel: bool = True
) -> None:
    """Função de conveniência para log warning"""
    logger_unificado.warning(mensagem, categoria, incluir_painel)


def log_error(
    mensagem: str, categoria: str = "sistema", incluir_painel: bool = True
) -> None:
    """Função de conveniência para log error"""
    logger_unificado.error(mensagem, categoria, incluir_painel)


def log_success(
    mensagem: str, categoria: str = "trading", incluir_painel: bool = True
) -> None:
    """Função de conveniência para log success"""
    logger_unificado.success(mensagem, categoria, incluir_painel)


def log_trading(
    mensagem: str, nivel: str = "info", incluir_painel: bool = True
) -> None:
    """Função de conveniência para log trading"""
    logger_unificado.trading(mensagem, nivel, incluir_painel)


def log_stops(
    mensagem: str, nivel: str = "warning", incluir_painel: bool = True
) -> None:
    """Função de conveniência para log de stops"""
    logger_unificado.stops(mensagem, nivel, incluir_painel)


def log_erro_critico(
    mensagem: str, erro: Exception = None, incluir_painel: bool = True
) -> None:
    """Função de conveniência para log de erro crítico"""
    logger_unificado.erro_critico(mensagem, erro, incluir_painel)


def log_sucesso_operacao(mensagem: str, incluir_painel: bool = True) -> None:
    """Função de conveniência para log de sucesso em operação"""
    logger_unificado.sucesso_operacao(mensagem, incluir_painel)
