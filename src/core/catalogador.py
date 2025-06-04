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
import importlib

from src import config
from .estrategia_turbo import (
    ESTRATEGIA_TURBO,
    ATIVOS_TURBO,
    ANALISE_TECNICA,
    obter_ativo_prioritario,
    validar_entrada,
    calcular_volume_entrada,
)

# Configuração de memória local
MEMORIA_DIR = "memoria"
if not os.path.exists(MEMORIA_DIR):
    os.makedirs(MEMORIA_DIR)


def carregar_memoria(arquivo):
    """Carrega dados de memória de um arquivo"""
    try:
        caminho = os.path.join(MEMORIA_DIR, arquivo)
        if os.path.exists(caminho):
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Erro ao carregar memória {arquivo}: {e}")
        return {}


def salvar_memoria(arquivo, dados):
    """Salva dados de memória em um arquivo"""
    try:
        caminho = os.path.join(MEMORIA_DIR, arquivo)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Erro ao salvar memória {arquivo}: {e}")


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
        "timeout": 5.0,  # Aumentado para reduzir timeouts
        "max_retries": 2,
        "retry_delay": 0.5,  # Aumentado para dar mais tempo
    },
    "analise": {
        "periodos": {
            "rsi": 14,
            "mm_curta": 9,
            "mm_longa": 21,
            "fibonacci": 10,
        },
        "limites": {
            "rsi_sobrevenda": 40,  # Mais agressivo - entra mais cedo
            "rsi_sobrecompra": 60,  # Mais agressivo - entra mais cedo
            "min_velas": 5,  # Muito menos velas - decisão rápida
            "max_latencia": 8.0,  # Aumentado para permitir IA funcionar
            "saida_duracao": 30,  # Saída mais rápida - 30 segundos
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
        # Força recarga do config para garantir que IA_CONFIG existe
        try:
            importlib.reload(config)
        except:
            pass

        # Verifica se IA_CONFIG existe, se não, cria um padrão
        if not hasattr(config, "IA_CONFIG"):
            config.IA_CONFIG = {
                "async_mode": False,
                "timeout": 5.0,  # Aumentado para reduzir timeouts
                "temperature": 0.1,
                "max_tokens": 5,
                "max_aguardar_consecutivo": 5,
            }

        # Carrega configurações de IA
        self.async_mode = config.IA_CONFIG.get("async_mode", False)
        self.timeout = config.IA_CONFIG.get(
            "timeout", 5.0
        )  # Aumentado para reduzir timeouts

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
    """Classe para tomada de decisões de trading com estratégia turbo fixa"""

    @staticmethod
    def analisar_entrada_turbo(
        velas: List[Dict],
        lucro_total: float,
        entradas_recentes: List[str],
        cliente_id: str = "default",
    ) -> Tuple[str, float]:
        """
        ESTRATÉGIA TURBO FIXA - 15 SEGUNDOS
        Análise baseada em EMA(8), EMA(21), RSI(14) e Bollinger(20,2)
        """
        try:
            if len(velas) < 25:  # Precisa de pelo menos 25 velas para análise
                return DecisaoTipo.AGUARDAR.value, 0.0

            # Calcula indicadores da estratégia turbo
            indicadores = DecisaoTrading._calcular_indicadores_turbo(velas)

            # Verifica condições de entrada CALL
            sinal_call, confianca_call = DecisaoTrading._verificar_sinal_call(
                indicadores, velas
            )

            # Verifica condições de entrada PUT
            sinal_put, confianca_put = DecisaoTrading._verificar_sinal_put(
                indicadores, velas
            )

            # Escolhe o sinal com maior confiança
            if (
                sinal_call
                and confianca_call >= ESTRATEGIA_TURBO["entrada"]["min_confianca"]
            ):
                if not sinal_put or confianca_call > confianca_put:
                    return DecisaoTipo.CALL.value, confianca_call

            if (
                sinal_put
                and confianca_put >= ESTRATEGIA_TURBO["entrada"]["min_confianca"]
            ):
                return DecisaoTipo.PUT.value, confianca_put

            return DecisaoTipo.AGUARDAR.value, max(confianca_call, confianca_put)

        except Exception as e:
            logger.error(f"Erro análise turbo: {str(e)}")
            return DecisaoTipo.AGUARDAR.value, 0.0

    @staticmethod
    def _calcular_indicadores_turbo(velas: List[Dict]) -> Dict:
        """Calcula todos os indicadores necessários para a estratégia turbo"""
        try:
            closes = [float(v["close"]) for v in velas]
            highs = [float(v["high"]) for v in velas]
            lows = [float(v["low"]) for v in velas]

            # EMA 8 e EMA 21
            ema8 = DecisaoTrading._calcular_ema(closes, 8)
            ema21 = DecisaoTrading._calcular_ema(closes, 21)

            # RSI 14
            rsi = AnalisadorTecnico.calcular_rsi(velas, 14)

            # Bollinger Bands (20, 2)
            bb_superior, bb_inferior, bb_media = DecisaoTrading._calcular_bollinger(
                closes, 20, 2
            )

            return {
                "ema8": ema8,
                "ema21": ema21,
                "rsi": rsi,
                "bb_superior": bb_superior,
                "bb_inferior": bb_inferior,
                "bb_media": bb_media,
                "preco_atual": closes[-1],
                "preco_anterior": closes[-2] if len(closes) > 1 else closes[-1],
            }
        except Exception as e:
            logger.error(f"Erro cálculo indicadores turbo: {str(e)}")
            return {}

    @staticmethod
    def _verificar_sinal_call(
        indicadores: Dict, velas: List[Dict]
    ) -> Tuple[bool, float]:
        """Verifica condições para sinal de CALL"""
        try:
            if not indicadores:
                return False, 0.0

            confianca = 0.0
            sinais_positivos = 0
            total_sinais = 3

            # 1. Cruzamento EMA: EMA8 > EMA21 (40% do peso)
            if indicadores["ema8"] > indicadores["ema21"]:
                confianca += 0.4
                sinais_positivos += 1

            # 2. RSI não sobrecomprado (30% do peso)
            if indicadores["rsi"] < ESTRATEGIA_TURBO["indicadores"]["rsi_sobrecompra"]:
                confianca += 0.3
                sinais_positivos += 1

            # 3. Preço próximo ou tocando banda inferior Bollinger (30% do peso)
            distancia_bb_inf = abs(
                indicadores["preco_atual"] - indicadores["bb_inferior"]
            )
            range_bb = indicadores["bb_superior"] - indicadores["bb_inferior"]
            if distancia_bb_inf <= (range_bb * 0.1):  # Dentro de 10% da banda inferior
                confianca += 0.3
                sinais_positivos += 1

            # Sinal válido se pelo menos 2 dos 3 sinais estão presentes
            sinal_valido = sinais_positivos >= 2

            return sinal_valido, confianca

        except Exception as e:
            logger.error(f"Erro verificação sinal CALL: {str(e)}")
            return False, 0.0

    @staticmethod
    def _verificar_sinal_put(
        indicadores: Dict, velas: List[Dict]
    ) -> Tuple[bool, float]:
        """Verifica condições para sinal de PUT"""
        try:
            if not indicadores:
                return False, 0.0

            confianca = 0.0
            sinais_positivos = 0
            total_sinais = 3

            # 1. Cruzamento EMA: EMA8 < EMA21 (40% do peso)
            if indicadores["ema8"] < indicadores["ema21"]:
                confianca += 0.4
                sinais_positivos += 1

            # 2. RSI não sobrevendido (30% do peso)
            if indicadores["rsi"] > ESTRATEGIA_TURBO["indicadores"]["rsi_sobrevenda"]:
                confianca += 0.3
                sinais_positivos += 1

            # 3. Preço próximo ou tocando banda superior Bollinger (30% do peso)
            distancia_bb_sup = abs(
                indicadores["preco_atual"] - indicadores["bb_superior"]
            )
            range_bb = indicadores["bb_superior"] - indicadores["bb_inferior"]
            if distancia_bb_sup <= (range_bb * 0.1):  # Dentro de 10% da banda superior
                confianca += 0.3
                sinais_positivos += 1

            # Sinal válido se pelo menos 2 dos 3 sinais estão presentes
            sinal_valido = sinais_positivos >= 2

            return sinal_valido, confianca

        except Exception as e:
            logger.error(f"Erro verificação sinal PUT: {str(e)}")
            return False, 0.0

    @staticmethod
    def _calcular_ema(precos: List[float], periodo: int) -> float:
        """Calcula EMA (Exponential Moving Average)"""
        try:
            if len(precos) < periodo:
                return sum(precos) / len(precos)  # SMA se dados insuficientes

            multiplier = 2 / (periodo + 1)
            ema = sum(precos[:periodo]) / periodo  # Primeira EMA é SMA

            for preco in precos[periodo:]:
                ema = (preco * multiplier) + (ema * (1 - multiplier))

            return ema
        except Exception as e:
            logger.error(f"Erro cálculo EMA: {str(e)}")
            return 0.0

    @staticmethod
    def _calcular_bollinger(
        precos: List[float], periodo: int, desvio: float
    ) -> Tuple[float, float, float]:
        """Calcula Bandas de Bollinger"""
        try:
            if len(precos) < periodo:
                media = sum(precos) / len(precos)
                return media, media, media

            # Média móvel simples
            sma = sum(precos[-periodo:]) / periodo

            # Desvio padrão
            variancia = sum((p - sma) ** 2 for p in precos[-periodo:]) / periodo
            std_dev = variancia**0.5

            # Bandas
            bb_superior = sma + (desvio * std_dev)
            bb_inferior = sma - (desvio * std_dev)

            return bb_superior, bb_inferior, sma
        except Exception as e:
            logger.error(f"Erro cálculo Bollinger: {str(e)}")
            return 0.0, 0.0, 0.0

    @staticmethod
    def analisar_entrada(
        velas: List[Dict],
        lucro_total: float,
        entradas_recentes: List[str],
        cliente_id: str = "default",
    ) -> str:
        """
        ESTRATÉGIA TURBO ATIVADA - Análise fixa de 15 segundos
        Usa EMA(8), EMA(21), RSI(14) e Bollinger(20,2) para decisões rápidas
        """
        try:
            # Usa a estratégia turbo fixa
            decisao, confianca = DecisaoTrading.analisar_entrada_turbo(
                velas, lucro_total, entradas_recentes, cliente_id
            )

            # Log da decisão com indicadores
            if len(velas) >= 25:
                indicadores = DecisaoTrading._calcular_indicadores_turbo(velas)
                try:
                    import main

                    if decisao == DecisaoTipo.CALL.value:
                        main.adicionar_log_tempo_real(
                            f"🟢 SINAL CALL - EMA8:{indicadores['ema8']:.2f} > EMA21:{indicadores['ema21']:.2f}, RSI:{indicadores['rsi']:.1f}, BB:{indicadores['preco_atual']:.2f}, Conf:{confianca:.1%}",
                            "success",
                        )
                    elif decisao == DecisaoTipo.PUT.value:
                        main.adicionar_log_tempo_real(
                            f"🔴 SINAL PUT - EMA8:{indicadores['ema8']:.2f} < EMA21:{indicadores['ema21']:.2f}, RSI:{indicadores['rsi']:.1f}, BB:{indicadores['preco_atual']:.2f}, Conf:{confianca:.1%}",
                            "success",
                        )
                    elif decisao == DecisaoTipo.AGUARDAR.value and confianca > 0.5:
                        main.adicionar_log_tempo_real(
                            f"⏳ AGUARDANDO - EMA8:{indicadores['ema8']:.2f}, EMA21:{indicadores['ema21']:.2f}, RSI:{indicadores['rsi']:.1f}, Conf:{confianca:.1%} (< 85%)",
                            "warning",
                        )
                except:
                    pass

            return decisao

        except Exception as e:
            logger.error(f"Erro análise entrada: {str(e)}")
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

            # REGRAS ULTRA AGRESSIVAS DE SAÍDA
            # Saída rápida com qualquer lucro após 15 segundos
            if contexto.duracao > 15 and contexto.lucro > 0.5:  # Qualquer lucro > 0.5%
                logger.info(
                    f"SCALPING: Saída rápida - {contexto.lucro:.2f}% em {contexto.duracao}s"
                )
                try:
                    import main

                    main.adicionar_log_tempo_real(
                        f"Saída rápida - {contexto.lucro:.2f}% em {contexto.duracao}s",
                        "success",
                    )
                except:
                    pass
                decisao = DecisaoTipo.SAIR.value

            # Stop loss agressivo - sai rápido para evitar perdas
            if contexto.lucro < -2.0:  # 2% de perda máxima
                logger.info(f"SCALPING: Stop loss rápido - {contexto.lucro:.2f}%")
                decisao = DecisaoTipo.SAIR.value

            # Take profit rápido - pega lucro pequeno mas garantido
            if contexto.lucro > 3.0:  # 3% de ganho = sai
                logger.info(f"SCALPING: Take profit rápido - {contexto.lucro:.2f}%")
                decisao = DecisaoTipo.SAIR.value

            # Saída forçada por tempo - não fica muito tempo em operação
            if contexto.duracao > limites["saida_duracao"]:  # 30 segundos máximo
                logger.info(f"SCALPING: Saída por tempo limite - {contexto.duracao}s")
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

        # Scanner de ativos para scalping
        self.ativo_atual = None
        self.scanner_ativo = True
        self.dados_ativos = {}  # Armazena dados de múltiplos ativos
        self.ultima_analise_scanner = 0
        self.intervalo_scanner = 60  # Analisa ativos a cada 60 segundos
        self.ativos_priorizados = []  # Lista de ativos ordenados por prioridade

        # Inicializa o logger específico
        self.logger = logging.getLogger("catalogador")
        self.logger.info(
            f"Catalogador iniciado (max_velas={self.max_velas}, retenção={self.max_data_age_seconds/3600}h)"
        )

    # --------- Sistema Inteligente de Operações Múltiplas ----------
    def analisar_scalping(
        self,
        cliente_id: str = "default",
        modo: str = "iniciante",
        meta: float = 100.0,
        lucro_atual: float = 0.0,
        operacoes_ativas: int = 0,
    ) -> dict:
        """Analisa as velas e retorna sinal inteligente baseado no modo e situação atual.

        Args:
            cliente_id: ID do cliente
            modo: Modo de operação (iniciante, conservador, agressivo)
            meta: Meta diária em dólares
            lucro_atual: Lucro atual acumulado
            operacoes_ativas: Número de operações abertas

        Retorna:
            {"sinal": "compra"|"venda"|None, "confianca": float(0-1), "razao": str,
             "lucro_esperado": float, "valor_entrada": float}
        """
        try:
            # Verifica se é hora de limpar dados antigos
            self._check_cleanup()

            # Configurações por modo
            config_modos = {
                "iniciante": {
                    "max_operacoes": 1,
                    "confianca_min": 0.85,
                    "valor_entrada_percent": 0.02,  # 2% da meta
                    "lucro_min_esperado": 0.2,
                    "meta_maxima": 20.0,
                    "meta_padrao": 20.0,
                },
                "conservador": {
                    "max_operacoes": 3,
                    "confianca_min": 0.80,
                    "valor_entrada_percent": 0.02,  # 2% da meta
                    "lucro_min_esperado": 0.2,
                    "meta_maxima": 50.0,
                    "meta_padrao": 50.0,
                },
                "agressivo": {
                    "max_operacoes": 5,
                    "confianca_min": 0.75,
                    "valor_entrada_percent": 0.02,  # 2% da meta
                    "lucro_min_esperado": 0.2,
                    "meta_maxima": None,  # Ilimitado
                    "meta_padrao": 100.0,
                },
            }

            config_atual = config_modos.get(modo, config_modos["iniciante"])

            # Validação da meta baseada no modo
            if (
                config_atual["meta_maxima"] is not None
                and meta > config_atual["meta_maxima"]
            ):
                return {
                    "sinal": None,
                    "confianca": 0.0,
                    "razao": f"Meta excede limite do modo {modo} (máx: ${config_atual['meta_maxima']:.0f})",
                    "lucro_esperado": 0.0,
                    "valor_entrada": 0.0,
                }

            # Verificações de segurança
            # 1. Meta já atingida
            if lucro_atual >= meta:
                return {
                    "sinal": None,
                    "confianca": 0.0,
                    "razao": "Meta diária já atingida",
                    "lucro_esperado": 0.0,
                    "valor_entrada": 0.0,
                }

            # 2. Limite de operações simultâneas
            if operacoes_ativas >= config_atual["max_operacoes"]:
                return {
                    "sinal": None,
                    "confianca": 0.0,
                    "razao": f"Limite de operações atingido ({operacoes_ativas}/{config_atual['max_operacoes']})",
                    "lucro_esperado": 0.0,
                    "valor_entrada": 0.0,
                }

            # 3. Dados insuficientes
            if len(self.velas) < CONFIG["analise"]["limites"]["min_velas"]:
                return {
                    "sinal": None,
                    "confianca": 0.0,
                    "razao": "Dados insuficientes",
                    "lucro_esperado": 0.0,
                    "valor_entrada": 0.0,
                }

            # Análise técnica aprimorada para microoperações
            analise_micro = self._analisar_microoperacao()

            # Usa a pipeline de decisão já implementada (IA + técnico)
            decisao, confianca = analisar_entrada_chatgpt(
                self.velas, lucro_atual, [], cliente_id
            )

            # Aplica boost de confiança baseado na análise micro
            confianca_ajustada = min(0.95, confianca + analise_micro["boost_confianca"])

            # Verifica confiança mínima para o modo
            if confianca_ajustada < config_atual["confianca_min"]:
                return {
                    "sinal": None,
                    "confianca": confianca_ajustada,
                    "razao": f"Confiança insuficiente ({confianca_ajustada:.2f} < {config_atual['confianca_min']:.2f})",
                    "lucro_esperado": 0.0,
                    "valor_entrada": 0.0,
                }

            # Obtém configurações específicas do ativo atual
            ativo_config = self._obter_config_ativo_scalping()
            min_stake_ativo = ativo_config.get("min_stake", 0.35)

            # Calcula valor da entrada e lucro esperado
            valor_entrada = max(
                min_stake_ativo, min(10.0, meta * config_atual["valor_entrada_percent"])
            )
            lucro_esperado = max(
                config_atual["lucro_min_esperado"], analise_micro["lucro_estimado"]
            )

            # Mapeia a decisão para o formato esperado pelo Motor
            if decisao == DecisaoTipo.CALL.value:
                sinal = "compra"
                razao = f"CALL: {analise_micro['razao_principal']}"
            elif decisao == DecisaoTipo.PUT.value:
                sinal = "venda"
                razao = f"PUT: {analise_micro['razao_principal']}"
            else:
                return {
                    "sinal": None,
                    "confianca": 0.0,
                    "razao": "Sem sinal claro",
                    "lucro_esperado": 0.0,
                    "valor_entrada": 0.0,
                }

            # Log da decisão
            self.logger.info(
                f"Scalping {modo.upper()}: {sinal} - Conf: {confianca_ajustada:.2f} - "
                f"Valor: ${valor_entrada:.2f} - Lucro esperado: ${lucro_esperado:.2f}"
            )

            return {
                "sinal": sinal,
                "confianca": confianca_ajustada,
                "razao": razao,
                "lucro_esperado": lucro_esperado,
                "valor_entrada": valor_entrada,
            }

        except Exception as e:
            self.logger.error(f"Erro na análise de scalping: {str(e)}", exc_info=True)
            return {
                "sinal": None,
                "confianca": 0.0,
                "razao": "Erro na análise",
                "lucro_esperado": 0.0,
                "valor_entrada": 0.0,
            }

    def _analisar_microoperacao(self) -> dict:
        """Análise técnica específica para microoperações de alta frequência"""
        try:
            if len(self.velas) < 10:
                return {
                    "boost_confianca": 0.0,
                    "lucro_estimado": 0.0,
                    "razao_principal": "Dados insuficientes",
                }

            # Pega as últimas 10 velas para análise rápida
            velas_recentes = self.velas[-10:]
            closes = [float(v["close"]) for v in velas_recentes]
            highs = [float(v["high"]) for v in velas_recentes]
            lows = [float(v["low"]) for v in velas_recentes]
            volumes = [float(v.get("volume", 1)) for v in velas_recentes]

            # Análise de volatilidade (essencial para microoperações)
            volatilidade = np.std(closes) if len(closes) > 1 else 0
            movimento_recente = abs(closes[-1] - closes[-2]) if len(closes) >= 2 else 0

            # Análise de momentum das últimas 5 velas
            momentum_alta = sum(
                1 for i in range(1, min(6, len(closes))) if closes[-i] > closes[-i - 1]
            )
            momentum_baixa = sum(
                1 for i in range(1, min(6, len(closes))) if closes[-i] < closes[-i - 1]
            )

            # Análise de volume (importante para confirmar movimentos)
            volume_medio = np.mean(volumes[-5:]) if len(volumes) >= 5 else volumes[-1]
            volume_atual = volumes[-1]
            volume_ratio = volume_atual / volume_medio if volume_medio > 0 else 1

            # RSI rápido (últimas 5 velas)
            if len(closes) >= 5:
                deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
                ganhos = [d for d in deltas if d > 0]
                perdas = [-d for d in deltas if d < 0]

                avg_ganho = np.mean(ganhos) if ganhos else 0
                avg_perda = np.mean(perdas) if perdas else 0

                if avg_perda > 0:
                    rs = avg_ganho / avg_perda
                    rsi_rapido = 100 - (100 / (1 + rs))
                else:
                    rsi_rapido = 100 if avg_ganho > 0 else 50
            else:
                rsi_rapido = 50

            # Cálculo do boost de confiança
            boost_confianca = 0.0
            razoes = []

            # Boost por volatilidade adequada (não muito alta, não muito baixa)
            if 0.0001 <= volatilidade <= 0.001:
                boost_confianca += 0.1
                razoes.append("volatilidade ideal")

            # Boost por momentum claro
            if momentum_alta >= 3:
                boost_confianca += 0.15
                razoes.append("momentum de alta")
            elif momentum_baixa >= 3:
                boost_confianca += 0.15
                razoes.append("momentum de baixa")

            # Boost por volume confirmando movimento
            if volume_ratio >= 1.2:
                boost_confianca += 0.1
                razoes.append("volume confirmando")

            # Boost por RSI em extremos (oportunidade de reversão)
            if rsi_rapido <= 30:
                boost_confianca += 0.1
                razoes.append("RSI oversold")
            elif rsi_rapido >= 70:
                boost_confianca += 0.1
                razoes.append("RSI overbought")

            # Estimativa de lucro baseada na volatilidade e movimento
            lucro_estimado = max(
                0.2, min(2.0, volatilidade * 1000 + movimento_recente * 500)
            )

            razao_principal = (
                ", ".join(razoes[:3]) if razoes else "análise técnica padrão"
            )

            return {
                "boost_confianca": boost_confianca,
                "lucro_estimado": lucro_estimado,
                "razao_principal": razao_principal,
            }

        except Exception as e:
            self.logger.error(f"Erro na análise micro: {str(e)}")
            return {
                "boost_confianca": 0.0,
                "lucro_estimado": 0.0,
                "razao_principal": "erro na análise",
            }

    def _obter_config_ativo_scalping(self) -> dict:
        """Obtém a configuração específica do ativo atual para scalping"""
        try:
            from src.core.config import ATIVOS_SCALPING

            # Usa o ativo atual do motor se disponível
            ativo_atual = getattr(self, "ativo_atual", "R_10")  # Default para R_10
            return ATIVOS_SCALPING.get(
                ativo_atual,
                {
                    "min_stake": 0.35,
                    "multipliers": [1, 2, 3, 4, 5, 10],
                    "contract_types": ["MULTUP", "MULTDOWN"],
                    "basis": "stake",
                    "duracao_padrao": 1,
                    "tipo_contrato": "multiplier",
                },
            )
        except Exception as e:
            self.logger.error(f"Erro ao obter config do ativo: {e}")
            return {
                "min_stake": 0.35,
                "multipliers": [1, 2, 3, 4, 5, 10],
                "contract_types": ["MULTUP", "MULTDOWN"],
                "basis": "stake",
                "duracao_padrao": 1,
                "tipo_contrato": "multiplier",
            }

    def verificar_protecao_operacoes(
        self, operacoes_abertas: list, meta: float, lucro_atual: float
    ) -> dict:
        """Verifica se deve proteger operações abertas ao parar o robô"""
        try:
            if not operacoes_abertas:
                return {"pode_parar": True, "razao": "Nenhuma operação aberta"}

            # Calcula lucro potencial das operações abertas
            lucro_potencial = 0.0
            operacoes_com_lucro = 0

            for op in operacoes_abertas:
                # Estima lucro baseado no tempo decorrido e movimento do preço
                tempo_decorrido = time.time() - op.get(
                    "timestamp_abertura", time.time()
                )

                # Se a operação está há mais de 20 segundos, provavelmente tem algum resultado
                if tempo_decorrido >= 20:
                    # Estima lucro positivo para operações que duraram tempo suficiente
                    lucro_estimado = 0.3  # Lucro conservador estimado
                    lucro_potencial += lucro_estimado
                    operacoes_com_lucro += 1

            # Se o lucro atual + potencial atinge a meta, pode parar
            if (lucro_atual + lucro_potencial) >= meta:
                return {
                    "pode_parar": True,
                    "razao": f"Lucro potencial atinge meta ({lucro_atual:.2f} + {lucro_potencial:.2f} >= {meta:.2f})",
                }

            # Se tem operações com potencial de lucro, aguarda
            if operacoes_com_lucro > 0:
                return {
                    "pode_parar": False,
                    "razao": f"{operacoes_com_lucro} operações com potencial de lucro",
                    "tempo_espera": 30,  # segundos para aguardar
                }

            # Se as operações são muito recentes, aguarda um pouco
            operacoes_recentes = [
                op
                for op in operacoes_abertas
                if (time.time() - op.get("timestamp_abertura", 0)) < 10
            ]

            if operacoes_recentes:
                return {
                    "pode_parar": False,
                    "razao": f"{len(operacoes_recentes)} operações muito recentes",
                    "tempo_espera": 15,
                }

            # Caso contrário, pode parar
            return {
                "pode_parar": True,
                "razao": "Operações sem potencial significativo",
            }

        except Exception as e:
            self.logger.error(f"Erro na verificação de proteção: {str(e)}")
            return {
                "pode_parar": True,
                "razao": "Erro na análise, parando por segurança",
            }

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
                    time.time() - vela_atual.get("timestamp")
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
        # Aumenta intervalo de limpeza para 60 segundos para evitar spam
        if current_time - self.last_cleanup_time > 60:  # 60 segundos
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
                if candle.get("timestamp") >= velas_cutoff_time
            ]
            velas_removed = old_velas_count - len(self.velas)

            # Se removeu algo, registra no log
            if ticks_removed > 0 or velas_removed > 0:
                self.logger.info(
                    f"Limpeza: {velas_removed} velas e {ticks_removed} ticks antigos removidos"
                )

            # Força limite máximo de velas apenas se exceder muito
            if len(self.velas) > self.max_velas * 2:  # 100% de margem
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

    # --------- Sistema de Scanner de Ativos para Scalping ----------
    def inicializar_scanner_ativos(self):
        """Inicializa o scanner de ativos com base na configuração"""
        try:
            from src.core.config import ATIVOS_SCALPING

            # Ordena ativos por prioridade (maior prioridade primeiro)
            self.ativos_priorizados = sorted(
                ATIVOS_SCALPING.items(), key=lambda x: x[1]["prioridade"], reverse=True
            )

            self.logger.info(
                f"Scanner inicializado com {len(self.ativos_priorizados)} ativos"
            )

            # Define o primeiro ativo como padrão
            if self.ativos_priorizados:
                self.ativo_atual = self.ativos_priorizados[0][0]
                self.logger.info(f"Ativo inicial selecionado: {self.ativo_atual}")

        except Exception as e:
            self.logger.error(f"Erro ao inicializar scanner: {e}")
            # Fallback para R_100
            self.ativo_atual = "R_100"

    def analisar_melhor_ativo(self) -> str:
        """Analisa todos os ativos e retorna o melhor para scalping no momento"""
        try:
            agora = time.time()

            # Verifica se é hora de fazer nova análise
            if agora - self.ultima_analise_scanner < self.intervalo_scanner:
                return self.ativo_atual or "R_100"

            self.ultima_analise_scanner = agora

            if not self.ativos_priorizados:
                self.inicializar_scanner_ativos()

            melhor_ativo = None
            melhor_score = 0

            # Analisa os top 5 ativos por prioridade
            for ativo, config in self.ativos_priorizados[:5]:
                score = self._calcular_score_ativo(ativo, config)

                if score > melhor_score:
                    melhor_score = score
                    melhor_ativo = ativo

            if melhor_ativo and melhor_ativo != self.ativo_atual:
                # Log mais informativo para o usuário
                from src.core.config import ATIVOS_SCALPING

                nome_ativo = ATIVOS_SCALPING.get(melhor_ativo, {}).get(
                    "nome", melhor_ativo
                )
                self.logger.info(
                    f"Scanner: {nome_ativo} selecionado (score: {melhor_score:.0f})"
                )
                self.ativo_atual = melhor_ativo

            return self.ativo_atual or "R_100"

        except Exception as e:
            self.logger.error(f"Erro na análise de ativos: {e}")
            return self.ativo_atual or "R_100"

    def _calcular_score_ativo(self, ativo: str, config: dict) -> float:
        """Calcula score de um ativo para scalping"""
        try:
            score = 0.0

            # Score base pela prioridade configurada
            score += config.get("prioridade", 5) * 10

            # Bonus por spread baixo
            spread = config.get("spread", "medio")
            if spread == "muito-baixo":
                score += 20
            elif spread == "baixo":
                score += 15
            elif spread == "medio":
                score += 10

            # Bonus por volatilidade adequada para scalping
            volatilidade = config.get("volatilidade", "media")
            if volatilidade in ["baixa", "media"]:
                score += 15  # Ideal para scalping
            elif volatilidade == "media-alta":
                score += 10
            elif volatilidade == "alta":
                score += 5
            else:  # muito-alta ou extrema
                score += 2  # Mais arriscado

            # Bonus por disponibilidade 24/7
            if config.get("horario") == "24/7":
                score += 10

            # Bonus por stake mínimo baixo
            min_stake = config.get("min_stake", 1.0)
            if min_stake <= 0.35:
                score += 15
            elif min_stake <= 0.5:
                score += 10
            elif min_stake <= 1.0:
                score += 5

            # Análise técnica se temos dados do ativo
            if ativo in self.dados_ativos and len(self.dados_ativos[ativo]) >= 5:
                dados = self.dados_ativos[ativo]

                # Calcula volatilidade recente
                precos = [d["close"] for d in dados[-5:]]
                if len(precos) >= 2:
                    volatilidade_real = np.std(precos) if len(precos) > 1 else 0

                    # Volatilidade ideal para scalping (nem muito alta, nem muito baixa)
                    if 0.0001 <= volatilidade_real <= 0.001:
                        score += 20
                    elif 0.00005 <= volatilidade_real <= 0.002:
                        score += 10

                # Verifica tendência clara (bom para scalping)
                if len(precos) >= 3:
                    tendencia_alta = all(
                        precos[i] >= precos[i - 1] for i in range(1, len(precos))
                    )
                    tendencia_baixa = all(
                        precos[i] <= precos[i - 1] for i in range(1, len(precos))
                    )

                    if tendencia_alta or tendencia_baixa:
                        score += 10  # Tendência clara é boa para scalping

            return score

        except Exception as e:
            self.logger.error(f"Erro ao calcular score do ativo {ativo}: {e}")
            return config.get("prioridade", 5) * 10  # Score básico

    def obter_ativo_recomendado(self) -> dict:
        """Retorna informações do ativo recomendado para scalping"""
        try:
            from src.core.config import ATIVOS_SCALPING

            ativo_atual = self.analisar_melhor_ativo()
            config_ativo = ATIVOS_SCALPING.get(ativo_atual, {})

            return {
                "ativo": ativo_atual,
                "nome": config_ativo.get("nome", ativo_atual),
                "min_stake": config_ativo.get("min_stake", 0.35),
                "max_stake": config_ativo.get("max_stake", 50000),
                "volatilidade": config_ativo.get("volatilidade", "media"),
                "spread": config_ativo.get("spread", "medio"),
                "prioridade": config_ativo.get("prioridade", 5),
                "razao": "Melhor ativo disponível para scalping",
            }

        except Exception as e:
            self.logger.error(f"Erro ao obter ativo recomendado: {e}")
            return {
                "ativo": "R_100",
                "nome": "Volatility 100 Index",
                "min_stake": 0.35,
                "max_stake": 50000,
                "volatilidade": "muito-alta",
                "spread": "baixo",
                "prioridade": 8,
                "razao": "Ativo padrão (fallback)",
            }

    def listar_ativos_disponiveis(self) -> list:
        """Lista todos os ativos disponíveis para scalping"""
        try:
            from src.core.config import ATIVOS_SCALPING

            ativos = []
            for ativo, config in ATIVOS_SCALPING.items():
                ativos.append(
                    {
                        "ativo": ativo,
                        "nome": config.get("nome", ativo),
                        "min_stake": config.get("min_stake", 0.35),
                        "volatilidade": config.get("volatilidade", "media"),
                        "spread": config.get("spread", "medio"),
                        "prioridade": config.get("prioridade", 5),
                        "horario": config.get("horario", "24/7"),
                    }
                )

            # Ordena por prioridade
            ativos.sort(key=lambda x: x["prioridade"], reverse=True)
            return ativos

        except Exception as e:
            self.logger.error(f"Erro ao listar ativos: {e}")
            return [{"ativo": "R_100", "nome": "Volatility 100 Index", "prioridade": 8}]

    def estatisticas(self) -> Dict:
        """Retorna estatísticas do catalogador para monitoramento."""
        return {
            "num_velas": len(self.velas),
            "num_ticks": len(self.ticks),
            "primeira_vela": self.velas[0].get("timestamp") if self.velas else None,
            "ultima_vela": self.velas[-1].get("timestamp") if self.velas else None,
            "periodo_segundos": (
                self.velas[-1].get("timestamp") - self.velas[0].get("timestamp")
                if len(self.velas) > 1
                else 0
            ),
            "memoria_estimada_kb": (len(self.velas) * 8 * 6 + len(self.ticks) * 16)
            / 1024,
        }
