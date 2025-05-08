import httpx
import json
import time
import os
import numpy as np
import logging
from functools import lru_cache
from dotenv import load_dotenv
from typing import List, Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import asyncio

# Novo import do arquivo de configurações globais
import config

from inteligencia import carregar_memoria, salvar_memoria

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("trading.log"), logging.StreamHandler()],
)
logger = logging.getLogger("trader")

# Carregamento de variáveis de ambiente
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    logger.warning(
        "API key não encontrada. Configure a variável DEEPSEEK_API_KEY no arquivo .env"
    )

# Configurações centralizadas
CONFIG = {
    "api": {
        "url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "timeout": 2.5,
        "max_retries": 3,
        "retry_delay": 0.3,
    },
    "analise": {
        "periodos": {
            "rsi": 14,
            "mm_curta": 9,
            "mm_longa": 21,
            "fibonacci": 10,
        },
        "limites": {
            "rsi_sobrevenda": 30,
            "rsi_sobrecompra": 70,
            "min_velas": 20,
            "max_latencia": 0.5,
            "saida_duracao": 60,
        },
    },
}


class DecisaoTipo(str, Enum):
    """Enumeração para tipos de decisões de trading"""

    CALL = "CALL"
    PUT = "PUT"
    AGUARDAR = "AGUARDAR"
    SAIR = "SAIR"
    MANTER = "MANTER"


@dataclass
class Contexto:
    """Classe para armazenar contexto de análise"""

    preco_atual: float
    fibonacci: Dict[str, float]
    rsi: float
    mhi: int
    tendencia: str
    volume: str
    volatilidade: float
    lucro_total: float
    historico: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Converte o contexto para dicionário"""
        return {
            "preco_atual": self.preco_atual,
            "fib": self.fibonacci,
            "rsi": self.rsi,
            "mhi": self.mhi,
            "tendencia": self.tendencia,
            "volume": self.volume,
            "volatilidade": self.volatilidade,
            "lucro_total": self.lucro_total,
            "historico": self.historico,
        }

    def gerar_relatorio(self) -> str:
        """Gera relatório formatado do contexto"""
        return f"""ANÁLISE DE ENTRADA:
- Fib 61.8%: {self.fibonacci.get('61.8%', 0):.2f}
- Preço: {self.preco_atual:.2f}
- RSI: {self.rsi:.1f}
- MHI: {self.mhi}
- Tendência: {self.tendencia}
- Volume: {self.volume}
- Volatilidade: {self.volatilidade:.2f}
- Lucro Sessão: ${self.lucro_total:.2f}
- Histórico: {self.historico}"""


@dataclass
class ContextoSaida:
    """Classe para armazenar contexto de decisão de saída"""

    duracao: int
    lucro: float
    rsi: float
    fibonacci: Dict[str, float]
    tendencia: str
    volatilidade: float

    def gerar_relatorio(self) -> str:
        """Gera relatório formatado do contexto de saída"""
        return f"""ANÁLISE DE SAÍDA:
- Lucro: {self.lucro:.2f}%
- RSI: {self.rsi:.1f}
- Fib: {self.fibonacci.get('61.8%', 0):.2f}
- Tendência: {self.tendencia}
- Volatilidade: {self.volatilidade:.2f}"""


class AnalisadorTecnico:
    """Classe para análise técnica de mercado"""

    @staticmethod
    @lru_cache(maxsize=50)
    def calcular_media_movel(
        velas: Tuple[Tuple[str, float, float, float, float, float]], periodo: int
    ) -> Optional[float]:
        """
        Calcula média móvel simples com cache para otimização
        Args:
            velas: Tupla de tuplas com dados OHLCV (imutável para cache)
            periodo: Período para cálculo da média
        Returns:
            Valor da média móvel ou None se dados insuficientes
        """
        try:
            closes = [v[4] for v in velas]  # close está no índice 4
            if len(closes) < periodo:
                return None
            return np.mean(closes[-periodo:])
        except Exception as e:
            logger.error(f"Erro cálculo média móvel: {str(e)}")
            return None

    @staticmethod
    def identificar_fibonacci(velas: List[Dict]) -> Dict[str, float]:
        """
        Calcula níveis de retração de Fibonacci
        Args:
            velas: Lista de velas para análise
        Returns:
            Dicionário com níveis-chave de Fibonacci
        """
        try:
            periodo = CONFIG["analise"]["periodos"]["fibonacci"]
            highs = [v["high"] for v in velas[-periodo:]]
            lows = [v["low"] for v in velas[-periodo:]]
            max_high = max(highs)
            min_low = min(lows)
            diferenca = max_high - min_low

            return {
                "23.6%": max_high - diferenca * 0.236,
                "38.2%": max_high - diferenca * 0.382,
                "50%": max_high - diferenca * 0.5,
                "61.8%": max_high - diferenca * 0.618,
            }
        except Exception as e:
            logger.error(f"Erro cálculo Fibonacci: {str(e)}")
            return {}

    @staticmethod
    def calcular_rsi(velas: List[Dict], periodo: Optional[int] = None) -> float:
        """
        Calcula Relative Strength Index (RSI)
        Args:
            velas: Lista de velas para análise
            periodo: Período para cálculo do RSI (opcional)
        Returns:
            Valor do RSI entre 0-100
        """
        if periodo is None:
            periodo = CONFIG["analise"]["periodos"]["rsi"]

        try:
            closes = [v["close"] for v in velas]
            if len(closes) <= periodo:
                logger.warning(f"Dados insuficientes para RSI: {len(closes)}/{periodo}")
                return 50.0

            deltas = np.diff(closes)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)

            avg_gain = np.mean(gains[-periodo:])
            avg_loss = np.mean(losses[-periodo:])

            if avg_loss < 0.0001:  # Evitar divisão por zero
                return 100.0

            rs = avg_gain / avg_loss
            return 100 - (100 / (1 + rs))
        except Exception as e:
            logger.error(f"Erro cálculo RSI: {str(e)}")
            return 50.0

    @staticmethod
    def padrao_mhi(velas: List[Dict]) -> int:
        """
        Identifica padrão MHI (Market Harmonic Index)
        Args:
            velas: Lista de velas para análise
        Returns:
            Score de direção das últimas 5 velas
        """
        try:
            return sum(1 if v["close"] > v["open"] else -1 for v in velas[-5:])
        except Exception as e:
            logger.error(f"Erro cálculo MHI: {str(e)}")
            return 0

    @classmethod
    def tendencia_velas(cls, velas: List[Dict]) -> str:
        """
        Determina tendência com base em médias móveis
        Args:
            velas: Lista de velas para análise
        Returns:
            'ALTA', 'BAIXA' ou 'INDEFINIDA' conforme tendência
        """
        try:
            # Converter para formato de tupla para usar com lru_cache
            velas_tuple = tuple(
                (str(i), v["open"], v["high"], v["low"], v["close"], v["volume"])
                for i, v in enumerate(velas)
            )

            mm_curta = cls.calcular_media_movel(
                velas_tuple, CONFIG["analise"]["periodos"]["mm_curta"]
            )
            mm_longa = cls.calcular_media_movel(
                velas_tuple, CONFIG["analise"]["periodos"]["mm_longa"]
            )

            if mm_curta is None or mm_longa is None:
                return "INDEFINIDA"

            return "ALTA" if mm_curta > mm_longa else "BAIXA"
        except Exception as e:
            logger.error(f"Erro análise tendência: {str(e)}")
            return "INDEFINIDA"

    @staticmethod
    def tendencia_volume(velas: List[Dict]) -> str:
        """
        Analisa tendência do volume
        Args:
            velas: Lista de velas com dados de volume
        Returns:
            'CRESCENTE', 'DECRESCENTE' ou 'ESTÁVEL'
        """
        try:
            if len(velas) < 3:
                return "ESTÁVEL"

            volumes = [v["volume"] for v in velas[-3:]]
            if volumes[-1] > volumes[0] * 1.1:  # 10% de aumento
                return "CRESCENTE"
            elif volumes[-1] < volumes[0] * 0.9:  # 10% de diminuição
                return "DECRESCENTE"
            else:
                return "ESTÁVEL"
        except Exception as e:
            logger.error(f"Erro análise volume: {str(e)}")
            return "ESTÁVEL"


class DeepseekAPI:
    """Classe para interação com a API DeepSeek"""

    _instance = None

    @classmethod
    def get_instance(cls) -> "DeepseekAPI":
        """Singleton para reutilização do cliente"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Inicializa o cliente HTTP"""
        # Carrega configurações de IA
        self.async_mode = config.IA_CONFIG.get("async_mode", False)
        self.timeout = config.IA_CONFIG.get("timeout", 2.5)

        # Cria cliente apropriado (síncrono ou assíncrono)
        if self.async_mode:
            self.client = httpx.AsyncClient(timeout=self.timeout)
        else:
            self.client = httpx.Client(timeout=self.timeout)

        self.headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }

        # Contador para decisões AGUARDAR consecutivas
        self.aguardar_consecutivo = 0
        self.ultima_decisao = None
        self.ultima_confianca = 0.0

        # Histórico de decisões para análise
        self.historico_decisoes = []
        self.max_historico = 100  # Limite para evitar crescimento excessivo

    def __del__(self):
        """Fecha o cliente HTTP quando o objeto é destruído"""
        if hasattr(self, "client"):
            if self.async_mode:
                # Para clientes assíncronos, não podemos fechar diretamente
                # O garbage collector deve lidar com isso
                pass
            else:
                self.client.close()

    def registrar_decisao(
        self,
        decisao: str,
        confianca: float,
        contexto: Dict,
        cliente_id: str = "default",
    ):
        """
        Registra uma decisão no histórico

        Args:
            decisao: Decisão tomada
            confianca: Nível de confiança
            contexto: Dados contextuais da decisão
            cliente_id: ID do cliente
        """
        registro = {
            "timestamp": time.time(),
            "decisao": decisao,
            "confianca": confianca,
            "cliente_id": cliente_id,
            "contexto": contexto,
        }

        # Adiciona ao histórico (limitando o tamanho)
        self.historico_decisoes.append(registro)
        if len(self.historico_decisoes) > self.max_historico:
            self.historico_decisoes = self.historico_decisoes[-self.max_historico :]

        # Opcionalmente, salva no arquivo de log específico do cliente
        try:
            log_dir = os.path.join(MEMORIA_DIR, "logs")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            log_file = os.path.join(log_dir, f"{cliente_id}_decisoes.log")
            with open(log_file, "a", encoding="utf-8") as f:
                log_entry = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {decisao} ({confianca:.2f})\n"
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Erro ao registrar decisão no log: {e}")

    async def chamar_api_async(
        self, mensagens: List[Dict], max_retries: Optional[int] = None
    ) -> Tuple[str, float]:
        """
        Versão assíncrona da interface com API DeepSeek
        Args:
            mensagens: Contexto para análise
            max_retries: Número máximo de tentativas (opcional)
        Returns:
            Tupla (decisão, confiança) da IA ou fallback seguro
        """
        if max_retries is None:
            max_retries = CONFIG["api"]["max_retries"]

        payload = {
            "model": CONFIG["api"]["model"],
            "messages": mensagens,
            "temperature": config.IA_CONFIG.get("temperature", 0.1),
            "max_tokens": config.IA_CONFIG.get("max_tokens", 5),
            "stop": ["\n"],
        }

        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    CONFIG["api"]["url"],
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout,
                )
                if response.status_code == 200:
                    response_json = response.json()
                    decisao = (
                        response_json["choices"][0]["message"]["content"]
                        .strip()
                        .upper()
                    )

                    # Tenta extrair confiança do response
                    confianca = 0.8  # Valor padrão
                    try:
                        # Tenta extrair probabilidade/score da resposta da IA, se disponível
                        if "score" in response_json["choices"][0]:
                            confianca = float(response_json["choices"][0]["score"])
                        elif "confidence" in response_json["choices"][0]:
                            confianca = float(response_json["choices"][0]["confidence"])
                        # Limita a confiança entre 0 e 1
                        confianca = max(0.0, min(1.0, confianca))
                    except (KeyError, ValueError, TypeError):
                        # Se não conseguir extrair, mantém o padrão
                        pass

                    # Verifica se é decisão AGUARDAR consecutiva
                    if decisao == DecisaoTipo.AGUARDAR.value:
                        self.aguardar_consecutivo += 1
                        if self.aguardar_consecutivo >= config.IA_CONFIG.get(
                            "max_aguardar_consecutivo", 5
                        ):
                            logger.warning(
                                f"Alerta: {self.aguardar_consecutivo} decisões AGUARDAR consecutivas. Possível mercado lateral ou problema."
                            )
                    else:
                        self.aguardar_consecutivo = 0

                    self.ultima_decisao = decisao
                    self.ultima_confianca = confianca

                    # Registra contexto simplificado da decisão
                    contexto_simples = {
                        "message": mensagens[-1]["content"] if mensagens else "",
                        "attempt": attempt + 1,
                        "async": True,
                    }
                    self.registrar_decisao(decisao, confianca, contexto_simples)

                    return decisao, confianca
                else:
                    logger.warning(
                        f"Resposta não-200: {response.status_code} - {response.text}"
                    )
            except Exception as e:
                logger.error(f"Erro API ({attempt+1}/{max_retries}): {str(e)}")

            # Esperar antes de tentar novamente
            if attempt < max_retries - 1:
                await asyncio.sleep(CONFIG["api"]["retry_delay"])

        return DecisaoTipo.AGUARDAR.value, 0.0

    def chamar_api(
        self, mensagens: List[Dict], max_retries: Optional[int] = None
    ) -> Tuple[str, float]:
        """
        Interface com API DeepSeek para análise de decisões
        Args:
            mensagens: Contexto para análise
            max_retries: Número máximo de tentativas (opcional)
        Returns:
            Tupla (decisão, confiança) da IA ou fallback seguro
        """
        if self.async_mode:
            # Não podemos executar async em um contexto síncrono diretamente
            logger.warning(
                "Modo assíncrono ativado, mas chamada síncrona solicitada. Usando httpx padrão."
            )

        if max_retries is None:
            max_retries = CONFIG["api"]["max_retries"]

        payload = {
            "model": CONFIG["api"]["model"],
            "messages": mensagens,
            "temperature": config.IA_CONFIG.get("temperature", 0.1),
            "max_tokens": config.IA_CONFIG.get("max_tokens", 5),
            "stop": ["\n"],
        }

        for attempt in range(max_retries):
            try:
                response = self.client.post(
                    CONFIG["api"]["url"],
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout,
                )
                if response.status_code == 200:
                    response_json = response.json()
                    decisao = (
                        response_json["choices"][0]["message"]["content"]
                        .strip()
                        .upper()
                    )

                    # Tenta extrair confiança do response
                    confianca = 0.8  # Valor padrão
                    try:
                        # Tenta extrair probabilidade/score da resposta da IA, se disponível
                        if "score" in response_json["choices"][0]:
                            confianca = float(response_json["choices"][0]["score"])
                        elif "confidence" in response_json["choices"][0]:
                            confianca = float(response_json["choices"][0]["confidence"])
                        # Limita a confiança entre 0 e 1
                        confianca = max(0.0, min(1.0, confianca))
                    except (KeyError, ValueError, TypeError):
                        # Se não conseguir extrair, mantém o padrão
                        pass

                    # Verifica se é decisão AGUARDAR consecutiva
                    if decisao == DecisaoTipo.AGUARDAR.value:
                        self.aguardar_consecutivo += 1
                        if self.aguardar_consecutivo >= config.IA_CONFIG.get(
                            "max_aguardar_consecutivo", 5
                        ):
                            logger.warning(
                                f"Alerta: {self.aguardar_consecutivo} decisões AGUARDAR consecutivas. Possível mercado lateral ou problema."
                            )
                    else:
                        self.aguardar_consecutivo = 0

                    self.ultima_decisao = decisao
                    self.ultima_confianca = confianca

                    # Registra contexto simplificado da decisão
                    contexto_simples = {
                        "message": mensagens[-1]["content"] if mensagens else "",
                        "attempt": attempt + 1,
                        "async": False,
                    }
                    self.registrar_decisao(decisao, confianca, contexto_simples)

                    return decisao, confianca
                else:
                    logger.warning(
                        f"Resposta não-200: {response.status_code} - {response.text}"
                    )
            except Exception as e:
                logger.error(f"Erro API ({attempt+1}/{max_retries}): {str(e)}")

            # Esperar antes de tentar novamente
            if attempt < max_retries - 1:
                time.sleep(CONFIG["api"]["retry_delay"])

        return DecisaoTipo.AGUARDAR.value, 0.0


class VerificadorDados:
    """Classe para validação de dados de entrada"""

    @staticmethod
    def validar_velas(velas: List[Dict]) -> bool:
        """
        Valida estrutura das velas
        Args:
            velas: Lista de velas para validação
        Returns:
            True se estrutura válida, False caso contrário
        """
        if not velas:
            logger.warning("Lista de velas vazia")
            return False

        required_keys = {"open", "high", "low", "close", "volume"}
        for i, vela in enumerate(velas):
            if not required_keys.issubset(vela.keys()):
                logger.warning(f"Vela {i} não contém todas as chaves obrigatórias")
                return False

            # Verificar valores numéricos
            for key in required_keys:
                if not isinstance(vela[key], (int, float)):
                    logger.warning(f"Vela {i}, campo {key} não é numérico")
                    return False

            # Verificar consistência dos dados
            if not (
                vela["low"] <= vela["open"] <= vela["high"]
                and vela["low"] <= vela["close"] <= vela["high"]
            ):
                logger.warning(f"Vela {i} possui dados inconsistentes")
                return False

        return True


class DecisaoTrading:
    """Classe para tomada de decisões de trading"""

    @staticmethod
    def analisar_entrada(
        velas: List[Dict],
        lucro_total: float,
        entradas_recentes: List[str],
        cliente_id: str = "default",
    ) -> str:
        """
        Toma decisão de entrada usando análise técnica e IA
        Args:
            velas: Lista de velas OHLCV
            lucro_total: Resultado acumulado da sessão
            entradas_recentes: Histórico de operações
            cliente_id: Identificador do cliente
        Returns:
            Decisão: CALL, PUT ou AGUARDAR
        """
        start_time = time.time()
        logger.info(f"Iniciando análise de entrada para cliente {cliente_id}")

        # Validar dados
        if (
            not VerificadorDados.validar_velas(velas)
            or len(velas) < CONFIG["analise"]["limites"]["min_velas"]
        ):
            logger.warning("Dados insuficientes ou inválidos para análise")
            return DecisaoTipo.AGUARDAR.value

        try:
            analise = AnalisadorTecnico()

            # Criar contexto estruturado
            contexto = Contexto(
                preco_atual=velas[-1]["close"],
                fibonacci=analise.identificar_fibonacci(velas),
                rsi=analise.calcular_rsi(velas),
                mhi=analise.padrao_mhi(velas),
                tendencia=analise.tendencia_velas(velas),
                volume=analise.tendencia_volume(velas),
                volatilidade=np.mean([v["high"] - v["low"] for v in velas[-5:]]),
                lucro_total=lucro_total,
                historico=entradas_recentes[-5:],
            )

            relatorio = contexto.gerar_relatorio()
            logger.debug(f"Relatório de análise:\n{relatorio}")

            # Tentar decisão baseada em IA
            api = DeepseekAPI.get_instance()
            resposta, confianca = api.chamar_api(
                [
                    {"role": "system", "content": "Decisão rápida: CALL/PUT/AGUARDAR"},
                    {"role": "user", "content": relatorio},
                ]
            )

            # Verifica a confiança mínima configurada
            min_confianca = config.IA_CONFIG.get("min_confianca", 0.6)
            if confianca < min_confianca:
                logger.info(
                    f"Confiança baixa ({confianca:.2f} < {min_confianca:.2f}), decidindo AGUARDAR"
                )
                decisao = DecisaoTipo.AGUARDAR.value
            # Interpretar resposta
            elif DecisaoTipo.CALL.value in resposta:
                decisao = DecisaoTipo.CALL.value
                logger.info(f"Decisão IA: CALL com confiança {confianca:.2f}")
            elif DecisaoTipo.PUT.value in resposta:
                decisao = DecisaoTipo.PUT.value
                logger.info(f"Decisão IA: PUT com confiança {confianca:.2f}")
            else:
                decisao = DecisaoTipo.AGUARDAR.value
                logger.info(f"Decisão IA: AGUARDAR com confiança {confianca:.2f}")

            # Fallback técnico aprimorado
            if decisao == DecisaoTipo.AGUARDAR.value:
                limites = CONFIG["analise"]["limites"]
                if (
                    contexto.rsi < limites["rsi_sobrevenda"]
                    and contexto.tendencia == "ALTA"
                    and contexto.volume == "CRESCENTE"
                ):
                    decisao = DecisaoTipo.CALL.value
                    logger.info(
                        "Fallback técnico: CALL baseado em RSI baixo + tendência alta + volume crescente"
                    )
                elif (
                    contexto.rsi > limites["rsi_sobrecompra"]
                    and contexto.tendencia == "BAIXA"
                    and contexto.volume == "CRESCENTE"
                ):
                    decisao = DecisaoTipo.PUT.value
                    logger.info(
                        "Fallback técnico: PUT baseado em RSI alto + tendência baixa + volume crescente"
                    )

            # Verificar latência
            latencia = time.time() - start_time
            if latencia > CONFIG["analise"]["limites"]["max_latencia"]:
                logger.warning(f"Latência alta: {latencia:.3f}s, decidindo AGUARDAR")
                decisao = DecisaoTipo.AGUARDAR.value

            # Log de performance
            salvar_memoria(
                cliente_id,
                {
                    "timestamp": time.time(),
                    "decisao": decisao,
                    "confianca": confianca,
                    "latencia": latencia,
                    "contexto": contexto.to_dict(),
                },
            )

            logger.info(f"Decisão final: {decisao} (latência: {latencia:.3f}s)")
            return decisao

        except Exception as e:
            logger.error(f"Erro análise entrada: {str(e)}", exc_info=True)
            return DecisaoTipo.AGUARDAR.value

    @staticmethod
    def analisar_saida(
        velas: List[Dict], lucro_atual: float, cliente_id: str = "default"
    ) -> str:
        """
        Toma decisão de saída usando análise técnica e IA
        Args:
            velas: Lista de velas OHLCV
            lucro_atual: Resultado da operação atual
            cliente_id: Identificador do cliente
        Returns:
            Decisão: SAIR ou MANTER
        """
        start_time = time.time()
        logger.info(f"Iniciando análise de saída para cliente {cliente_id}")

        try:
            if not VerificadorDados.validar_velas(velas):
                logger.warning("Dados inválidos para análise de saída")
                return DecisaoTipo.SAIR.value

            analise = AnalisadorTecnico()

            # Criar contexto estruturado
            contexto = ContextoSaida(
                duracao=len(velas),
                lucro=lucro_atual,
                rsi=analise.calcular_rsi(velas),
                fibonacci=analise.identificar_fibonacci(velas),
                tendencia=analise.tendencia_velas(velas),
                volatilidade=np.mean([v["high"] - v["low"] for v in velas[-3:]]),
            )

            relatorio = contexto.gerar_relatorio()
            logger.debug(f"Relatório de saída:\n{relatorio}")

            # Decisão baseada em IA
            api = DeepseekAPI.get_instance()
            resposta, confianca = api.chamar_api(
                [
                    {"role": "system", "content": "Decisão rápida: SAIR/MANTER"},
                    {"role": "user", "content": relatorio},
                ]
            )

            # Verifica a confiança mínima configurada
            min_confianca = config.IA_CONFIG.get("min_confianca", 0.6)
            if confianca < min_confianca:
                logger.info(
                    f"Confiança baixa ({confianca:.2f} < {min_confianca:.2f}), decidindo SAIR por precaução"
                )
                decisao = DecisaoTipo.SAIR.value
            elif DecisaoTipo.SAIR.value in resposta:
                decisao = DecisaoTipo.SAIR.value
                logger.info(f"Decisão IA: SAIR com confiança {confianca:.2f}")
            else:
                decisao = DecisaoTipo.MANTER.value
                logger.info(f"Decisão IA: MANTER com confiança {confianca:.2f}")

            # Regras de saída
            limites = CONFIG["analise"]["limites"]

            # Regras de proteção
            if contexto.duracao > limites["saida_duracao"] and contexto.lucro > 0:
                logger.info(f"Saída por tempo: {contexto.duracao}s com lucro positivo")
                decisao = DecisaoTipo.SAIR.value

            # Evitar grandes perdas (stop loss)
            if contexto.lucro < -5.0:  # 5% de perda
                logger.info(f"Stop loss acionado: {contexto.lucro:.2f}%")
                decisao = DecisaoTipo.SAIR.value

            # Take profit
            if contexto.lucro > 7.0:  # 7% de ganho
                logger.info(f"Take profit acionado: {contexto.lucro:.2f}%")
                decisao = DecisaoTipo.SAIR.value

            # Log de performance
            latencia = time.time() - start_time
            logger.info(f"Decisão saída: {decisao} (latência: {latencia:.3f}s)")

            return decisao

        except Exception as e:
            logger.error(f"Erro análise saída: {str(e)}", exc_info=True)
            return DecisaoTipo.SAIR.value


# Interfaces compatíveis com o código original
def analisar_entrada_chatgpt(
    velas: List[Dict],
    lucro_total: float,
    entradas_recentes: List[str],
    cliente_id: str = "default",
) -> Tuple[str, float]:
    """
    Wrapper compatível com a interface original

    Returns:
        Uma tupla (decisão, confiança)
    """
    # Chamamos a implementação da classe, mas ignoramos a confiança por compatibilidade
    decisao = DecisaoTrading.analisar_entrada(
        velas, lucro_total, entradas_recentes, cliente_id
    )

    # Tenta recuperar a confiança da última chamada da API
    api = DeepseekAPI.get_instance()
    confianca = 0.7  # Valor padrão de fallback se não conseguirmos recuperar

    # Se o API tiver um valor de confiança salvo da última chamada, usa-o
    if hasattr(api, "ultima_confianca"):
        confianca = api.ultima_confianca

    return decisao, confianca


async def analisar_entrada_chatgpt_async(
    velas: List[Dict],
    lucro_total: float,
    entradas_recentes: List[str],
    cliente_id: str = "default",
) -> Tuple[str, float]:
    """
    Versão assíncrona do wrapper para análise de entrada

    Returns:
        Uma tupla (decisão, confiança)
    """
    # Obtém a instância do API para uso assíncrono
    api = DeepseekAPI.get_instance()

    # Verifica se o async_mode está configurado
    if not api.async_mode:
        # Se não estiver no modo assíncrono, chama o método síncrono
        return analisar_entrada_chatgpt(
            velas, lucro_total, entradas_recentes, cliente_id
        )

    try:
        # Prepara o contexto estruturado para análise
        analise = AnalisadorTecnico()

        # Criar contexto estruturado
        contexto = Contexto(
            preco_atual=velas[-1]["close"],
            fibonacci=analise.identificar_fibonacci(velas),
            rsi=analise.calcular_rsi(velas),
            mhi=analise.padrao_mhi(velas),
            tendencia=analise.tendencia_velas(velas),
            volume=analise.tendencia_volume(velas),
            volatilidade=np.mean([v["high"] - v["low"] for v in velas[-5:]]),
            lucro_total=lucro_total,
            historico=entradas_recentes[-5:],
        )

        relatorio = contexto.gerar_relatorio()

        # Chama a API de forma assíncrona
        decisao, confianca = await api.chamar_api_async(
            [
                {"role": "system", "content": "Decisão rápida: CALL/PUT/AGUARDAR"},
                {"role": "user", "content": relatorio},
            ]
        )

        # Registra a decisão na última vela para histórico
        if len(velas) > 0:
            vela_atual = velas[-1]
            if "ia_decisoes" not in vela_atual:
                vela_atual["ia_decisoes"] = []

            vela_atual["ia_decisoes"].append(
                {
                    "timestamp": time.time(),
                    "decisao": decisao,
                    "confianca": confianca,
                    "tipo": "entrada",
                    "cliente_id": cliente_id,
                }
            )

        return decisao, confianca

    except Exception as e:
        logger.error(f"Erro em análise assíncrona: {str(e)}", exc_info=True)
        return DecisaoTipo.AGUARDAR.value, 0.0


def analisar_saida_chatgpt(
    velas: List[Dict], lucro_atual: float, cliente_id: str = "default"
) -> Tuple[str, float]:
    """
    Wrapper compatível com a interface original para análise de saída

    Returns:
        Uma tupla (decisão, confiança)
    """
    # Chamamos a implementação da classe, mas ignoramos a confiança por compatibilidade
    decisao = DecisaoTrading.analisar_saida(velas, lucro_atual, cliente_id)

    # Tenta recuperar a confiança da última chamada da API
    api = DeepseekAPI.get_instance()
    confianca = 0.7  # Valor padrão de fallback se não conseguirmos recuperar

    # Se o API tiver um valor de confiança salvo da última chamada, usa-o
    if hasattr(api, "ultima_confianca"):
        confianca = api.ultima_confianca

    return decisao, confianca


async def analisar_saida_chatgpt_async(
    velas: List[Dict], lucro_atual: float, cliente_id: str = "default"
) -> Tuple[str, float]:
    """
    Versão assíncrona do wrapper para análise de saída

    Returns:
        Uma tupla (decisão, confiança)
    """
    # Obtém a instância do API para uso assíncrono
    api = DeepseekAPI.get_instance()

    # Verifica se o async_mode está configurado
    if not api.async_mode:
        # Se não estiver no modo assíncrono, chama o método síncrono
        return analisar_saida_chatgpt(velas, lucro_atual, cliente_id)

    try:
        # Prepara o contexto estruturado para análise
        analise = AnalisadorTecnico()

        # Criar contexto estruturado
        contexto = ContextoSaida(
            duracao=len(velas),
            lucro=lucro_atual,
            rsi=analise.calcular_rsi(velas),
            fibonacci=analise.identificar_fibonacci(velas),
            tendencia=analise.tendencia_velas(velas),
            volatilidade=np.mean([v["high"] - v["low"] for v in velas[-3:]]),
        )

        relatorio = contexto.gerar_relatorio()

        # Chama a API de forma assíncrona
        decisao, confianca = await api.chamar_api_async(
            [
                {"role": "system", "content": "Decisão rápida: SAIR/MANTER"},
                {"role": "user", "content": relatorio},
            ]
        )

        # Registra a decisão na última vela para histórico
        if len(velas) > 0:
            vela_atual = velas[-1]
            if "ia_decisoes" not in vela_atual:
                vela_atual["ia_decisoes"] = []

            vela_atual["ia_decisoes"].append(
                {
                    "timestamp": time.time(),
                    "decisao": decisao,
                    "confianca": confianca,
                    "tipo": "saida",
                    "cliente_id": cliente_id,
                    "lucro_atual": lucro_atual,
                }
            )

        return decisao, confianca

    except Exception as e:
        logger.error(f"Erro em análise de saída assíncrona: {str(e)}", exc_info=True)
        return DecisaoTipo.SAIR.value, 0.0


# Função para testes
def executar_teste(velas_teste: List[Dict]) -> None:
    """Executa um teste rápido do sistema"""
    logger.info("Iniciando teste do sistema...")

    if not VerificadorDados.validar_velas(velas_teste):
        logger.error("Dados de teste inválidos")
        return

    # Análise de entrada
    decisao, confianca = analisar_entrada_chatgpt(
        velas_teste, 0.0, ["CALL", "PUT", "AGUARDAR"]
    )
    logger.info(f"Teste de entrada: {decisao} (confiança: {confianca:.2f})")

    # Análise de saída
    decisao_saida, confianca_saida = analisar_saida_chatgpt(velas_teste, 2.5)
    logger.info(f"Teste de saída: {decisao_saida} (confiança: {confianca_saida:.2f})")

    logger.info("Teste concluído")


class Catalogador:
    def __init__(self):
        # Timeframe (em segundos) definido em config.py
        self.timeframe: int = max(1, int(getattr(config, "TIMEFRAME", 1)))

        # Lista bruta de ticks [(timestamp, preco)] para fins de depuração
        self.ticks: List[Tuple[float, float]] = []

        # Velas OHLCV já consolidadas
        self.velas: List[Dict[str, Union[int, float]]] = []

        # Estado da vela em construção
        self._current_candle: Optional[Dict[str, Union[int, float]]] = None
        self._current_candle_start: Optional[int] = None

        # Carrega configurações de armazenamento
        armazenamento_config = getattr(config, "ARMAZENAMENTO", {})

        # Tempo máximo para armazenar dados (6 horas por padrão)
        self.max_data_age_seconds = armazenamento_config.get(
            "max_duracao_velas", 6 * 60 * 60
        )

        # Tempo máximo para armazenar ticks brutos (1 hora por padrão)
        self.max_ticks_age_seconds = armazenamento_config.get(
            "max_duracao_ticks", 1 * 60 * 60
        )

        # Limite de velas e ticks a armazenar
        self.max_velas = armazenamento_config.get("max_velas", 1000)
        self.max_ticks = armazenamento_config.get("max_ticks", 1000)

        # Timestamp da última limpeza
        self.last_cleanup_time = time.time()

        # Intervalo para limpeza automática (a cada 30 minutos)
        self.cleanup_interval = armazenamento_config.get("intervalo_limpeza", 30 * 60)

        # Inicializa o logger específico
        self.logger = logging.getLogger("catalogador")
        self.logger.info(
            f"Catalogador iniciado (max_velas={self.max_velas}, retenção={self.max_data_age_seconds/3600}h)"
        )

    # --------- Novo método usado pelo Motor para decidir entradas ----------
    def analisar_scalping(self, cliente_id: str = "default") -> dict:
        """Analisa as velas acumuladas e retorna um sinal de CALL/PUT ou None.

        Retorna:
            {"sinal": "compra"|"venda"|None, "confianca": float(0-1), "razao": str}
        """
        try:
            # Verifica se é hora de limpar dados antigos
            self._check_cleanup()

            # Precisamos de pelo menos 20 velas para a IA tomar decisão
            if len(self.velas) < CONFIG["analise"]["limites"]["min_velas"]:
                return {"sinal": None, "confianca": 0.0, "razao": "Dados insuficientes"}

            # Usa a pipeline de decisão já implementada (IA + técnico)
            decisao, confianca = analisar_entrada_chatgpt(
                self.velas, 0.0, [], cliente_id
            )

            # Mapeia a decisão para o formato esperado pelo Motor
            if decisao == DecisaoTipo.CALL.value:
                sinal = "compra"
                razao = "Tendência de alta identificada"
            elif decisao == DecisaoTipo.PUT.value:
                sinal = "venda"
                razao = "Tendência de queda identificada"
            else:
                return {"sinal": None, "confianca": 0.0, "razao": "Sem sinal claro"}

            # Log da decisão
            self.logger.info(
                f"Scalping: Sinal de {sinal} detectado com confiança {confianca:.2f}"
            )

            return {
                "sinal": sinal,
                "confianca": confianca,
                "razao": razao,
            }
        except Exception as e:
            self.logger.error(f"Erro em analisar_scalping: {e}", exc_info=True)
            return {"sinal": None, "confianca": 0.0, "razao": f"Erro: {str(e)}"}

    def adicionar_tick(self, preco):
        """Adiciona um tick de preço e consolida em velas do timeframe definido.

        Args:
            preco (float): Último preço cotado.
        """
        try:
            # Marca temporal do tick (segundos desde epoch)
            ts: float = time.time()

            # Verifica se é hora de limpar dados antigos
            self._check_cleanup()

            # Salva tick bruto para auditoria/depuração (mantém apenas os últimos max_ticks)
            self.ticks.append((ts, preco))
            if len(self.ticks) > self.max_ticks:
                self.ticks = self.ticks[-self.max_ticks :]

            # Determina o início da vela corrente (alinha ao timeframe)
            candle_start: int = int(ts // self.timeframe * self.timeframe)

            # Se ainda não existe vela aberta, cria uma nova
            if self._current_candle is None:
                self._current_candle_start = candle_start
                self._current_candle = {
                    "timestamp": candle_start,
                    "open": preco,
                    "high": preco,
                    "low": preco,
                    "close": preco,
                    "volume": 1,
                }
                return

            # Caso o tick ainda pertença à janela da vela atual
            if candle_start == self._current_candle_start:
                self._current_candle["high"] = max(self._current_candle["high"], preco)
                self._current_candle["low"] = min(self._current_candle["low"], preco)
                self._current_candle["close"] = preco
                self._current_candle["volume"] += 1
            else:
                # Vela atual é finalizada e armazenada
                self.velas.append(self._current_candle)

                # Inicia uma nova vela com o tick recebido
                self._current_candle_start = candle_start
                self._current_candle = {
                    "timestamp": candle_start,
                    "open": preco,
                    "high": preco,
                    "low": preco,
                    "close": preco,
                    "volume": 1,
                }

                # Limpa dados antigos imediatamente se temos muitas velas
                if len(self.velas) > self.max_velas / 2:
                    self._cleanup_old_data()
        except Exception as e:
            self.logger.error(f"Erro ao adicionar tick: {e}", exc_info=True)

    def obter_velas(self):
        """Retorna as velas já processadas, incluindo a vela atual em formação."""
        try:
            # Verifica se é hora de limpar dados antigos
            self._check_cleanup()

            # Cria uma cópia das velas armazenadas para evitar race conditions
            result = list(self.velas)

            # Adiciona a vela atual se existir
            if self._current_candle is not None:
                result.append(dict(self._current_candle))

            return result
        except Exception as e:
            self.logger.error(f"Erro ao obter velas: {e}", exc_info=True)
            return list(self.velas)  # Retorna apenas as velas fechadas em caso de erro

    def obter_velas_preview(
        self, num_velas: int = None, incluir_em_formacao: bool = True
    ):
        """
        Retorna as últimas N velas, incluindo dados preliminares da vela em formação.

        Args:
            num_velas: Número de velas a retornar. Se None, retorna todas.
            incluir_em_formacao: Se True, inclui a vela atual mesmo que não esteja fechada.

        Returns:
            Lista de velas OHLCV, possivelmente incluindo a vela em formação.
        """
        try:
            # Verifica se é hora de limpar dados antigos
            self._check_cleanup()

            # Obtém velas fechadas
            result = list(self.velas)

            # Limita ao número solicitado
            if num_velas is not None and len(result) > num_velas:
                if incluir_em_formacao:
                    # Se vamos incluir a vela em formação, deixamos espaço para ela
                    result = result[-(num_velas - 1) :]
                else:
                    result = result[-num_velas:]

            # Adiciona a vela atual em formação, se solicitado
            if incluir_em_formacao and self._current_candle is not None:
                # Faz uma cópia para não modificar o original
                vela_atual = dict(self._current_candle)
                # Adiciona metadados para indicar que é uma vela em formação
                vela_atual["em_formacao"] = True
                vela_atual["progresso"] = (
                    time.time() - vela_atual["timestamp"]
                ) / self.timeframe
                result.append(vela_atual)

            # Adiciona metadados sobre a fonte dos dados
            for vela in result:
                if "em_formacao" not in vela:
                    vela["em_formacao"] = False

            self.logger.debug(
                f"Preview: {len(result)} velas retornadas (incluindo_formacao={incluir_em_formacao})"
            )
            return result

        except Exception as e:
            self.logger.error(f"Erro ao obter preview de velas: {e}", exc_info=True)
            return list(self.velas)  # Fallback seguro

    def limpar_dados(self):
        """Limpa todos os dados armazenados."""
        try:
            self.ticks.clear()
            self.velas.clear()
            self._current_candle = None
            self._current_candle_start = None
            self.last_cleanup_time = time.time()
            self.logger.info("Todos os dados foram limpos")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao limpar dados: {e}", exc_info=True)
            return False

    def _check_cleanup(self):
        """Verifica se é hora de limpar dados antigos."""
        current_time = time.time()
        if current_time - self.last_cleanup_time > self.cleanup_interval:
            self._cleanup_old_data()
            self.last_cleanup_time = current_time

    def _cleanup_old_data(self):
        """Limpa dados mais antigos que o limite configurado."""
        try:
            current_time = time.time()

            # Limpa ticks antigos (1 hora)
            ticks_cutoff_time = current_time - self.max_ticks_age_seconds
            old_ticks_count = len(self.ticks)
            self.ticks = [
                (ts, price) for ts, price in self.ticks if ts >= ticks_cutoff_time
            ]
            ticks_removed = old_ticks_count - len(self.ticks)

            # Limpa velas antigas (6 horas)
            velas_cutoff_time = current_time - self.max_data_age_seconds
            old_velas_count = len(self.velas)
            self.velas = [
                candle
                for candle in self.velas
                if candle["timestamp"] >= velas_cutoff_time
            ]
            velas_removed = old_velas_count - len(self.velas)

            # Se removeu algo, registra no log
            if ticks_removed > 0 or velas_removed > 0:
                self.logger.info(
                    f"Limpeza: {velas_removed} velas e {ticks_removed} ticks antigos removidos"
                )

            # Força limite máximo de velas mesmo que não sejam antigas
            if len(self.velas) > self.max_velas:
                excess = len(self.velas) - self.max_velas
                self.velas = self.velas[excess:]
                self.logger.info(
                    f"Limpeza por limite: {excess} velas removidas (limite máximo: {self.max_velas})"
                )

            # Força limite máximo de ticks mesmo que não sejam antigos
            if len(self.ticks) > self.max_ticks:
                excess = len(self.ticks) - self.max_ticks
                self.ticks = self.ticks[excess:]

            # Estima uso de memória
            velas_size = len(self.velas) * 8 * 6  # 6 valores float por vela (~48 bytes)
            ticks_size = len(self.ticks) * (8 + 8)  # timestamp + preço (16 bytes)
            total_size_kb = (velas_size + ticks_size) / 1024
            self.logger.debug(
                f"Uso de memória estimado: {total_size_kb:.2f} KB - Velas: {len(self.velas)}, Ticks: {len(self.ticks)}"
            )

            return True
        except Exception as e:
            self.logger.error(f"Erro durante limpeza de dados: {e}", exc_info=True)
            return False

    def estatisticas(self) -> Dict:
        """Retorna estatísticas do catalogador para monitoramento."""
        return {
            "num_velas": len(self.velas),
            "num_ticks": len(self.ticks),
            "primeira_vela": self.velas[0]["timestamp"] if self.velas else None,
            "ultima_vela": self.velas[-1]["timestamp"] if self.velas else None,
            "periodo_segundos": (
                self.velas[-1]["timestamp"] - self.velas[0]["timestamp"]
                if len(self.velas) > 1
                else 0
            ),
            "memoria_estimada_kb": (len(self.velas) * 8 * 6 + len(self.ticks) * 16)
            / 1024,
        }
