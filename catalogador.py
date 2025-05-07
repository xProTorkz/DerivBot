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
        self.client = httpx.Client(timeout=CONFIG["api"]["timeout"])
        self.headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }

    def __del__(self):
        """Fecha o cliente HTTP quando o objeto é destruído"""
        if hasattr(self, "client"):
            self.client.close()

    def chamar_api(
        self, mensagens: List[Dict], max_retries: Optional[int] = None
    ) -> str:
        """
        Interface com API DeepSeek para análise de decisões
        Args:
            mensagens: Contexto para análise
            max_retries: Número máximo de tentativas (opcional)
        Returns:
            Decisão da IA ou fallback seguro
        """
        if max_retries is None:
            max_retries = CONFIG["api"]["max_retries"]

        payload = {
            "model": CONFIG["api"]["model"],
            "messages": mensagens,
            "temperature": 0.1,
            "max_tokens": 5,
            "stop": ["\n"],
        }

        for attempt in range(max_retries):
            try:
                response = self.client.post(
                    CONFIG["api"]["url"],
                    headers=self.headers,
                    json=payload,
                    timeout=CONFIG["api"]["timeout"],
                )
                if response.status_code == 200:
                    return (
                        response.json()["choices"][0]["message"]["content"]
                        .strip()
                        .upper()
                    )
                else:
                    logger.warning(
                        f"Resposta não-200: {response.status_code} - {response.text}"
                    )
            except Exception as e:
                logger.error(f"Erro API ({attempt+1}/{max_retries}): {str(e)}")

            # Esperar antes de tentar novamente
            if attempt < max_retries - 1:
                time.sleep(CONFIG["api"]["retry_delay"])

        return "AGUARDAR"


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
            resposta = api.chamar_api(
                [
                    {"role": "system", "content": "Decisão rápida: CALL/PUT/AGUARDAR"},
                    {"role": "user", "content": relatorio},
                ]
            )

            # Interpretar resposta
            if DecisaoTipo.CALL.value in resposta:
                decisao = DecisaoTipo.CALL.value
            elif DecisaoTipo.PUT.value in resposta:
                decisao = DecisaoTipo.PUT.value
            else:
                decisao = DecisaoTipo.AGUARDAR.value

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
            resposta = api.chamar_api(
                [
                    {"role": "system", "content": "Decisão rápida: SAIR/MANTER"},
                    {"role": "user", "content": relatorio},
                ]
            )

            decisao = (
                DecisaoTipo.SAIR.value
                if DecisaoTipo.SAIR.value in resposta
                else DecisaoTipo.MANTER.value
            )

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
) -> str:
    """Wrapper compatível com a interface original"""
    return DecisaoTrading.analisar_entrada(
        velas, lucro_total, entradas_recentes, cliente_id
    )


def analisar_saida_chatgpt(
    velas: List[Dict], lucro_atual: float, cliente_id: str = "default"
) -> str:
    """Wrapper compatível com a interface original"""
    return DecisaoTrading.analisar_saida(velas, lucro_atual, cliente_id)


# Função para testes
def executar_teste(velas_teste: List[Dict]) -> None:
    """Executa um teste rápido do sistema"""
    logger.info("Iniciando teste do sistema...")

    if not VerificadorDados.validar_velas(velas_teste):
        logger.error("Dados de teste inválidos")
        return

    # Análise de entrada
    decisao = analisar_entrada_chatgpt(velas_teste, 0.0, ["CALL", "PUT", "AGUARDAR"])
    logger.info(f"Teste de entrada: {decisao}")

    # Análise de saída
    decisao_saida = analisar_saida_chatgpt(velas_teste, 2.5)
    logger.info(f"Teste de saída: {decisao_saida}")

    logger.info("Teste concluído")


class Catalogador:
    def __init__(self):
        self.ticks = []
        self.velas = []

    def adicionar_tick(self, preco):
        self.ticks.append(preco)
        # Aqui você pode implementar a lógica de transformar ticks em velas

    def obter_velas(self):
        # Retorna as velas já processadas
        return self.velas

    def limpar_dados(self):
        self.ticks = []
        self.velas = []
