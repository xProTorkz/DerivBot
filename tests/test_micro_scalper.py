"""
Testes Unitários Automatizados do Micro-Scalper Seletivo
Issues #2, #3, #4 - DerivBot

Critérios testados:
1. Zero Random / 100% Determinismo
2. Não comprar queda sem confirmação de reversão
3. Score de confluência >= 85
4. Gateway de risco (MAX_OPEN_POSITIONS = 1, Cooldown, Stale ticks, Saldo)
5. Saída no Primeiro Lucro Líquido (FIRST_POSITIVE_PROFIT) via Replay
"""

import os
import sys
import time
import unittest
import numpy as np

# Adiciona raiz do projeto ao path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.config.config import Config, MICRO_SCALPER_CONFIG
from src.core.catalogador import CatalogadorOtimizado, AnalisadorTecnicoOtimizado
from src.core.inteligencia import (
    ExtremeDetector,
    ReversalConfirmator,
    ConfluenceScore,
    MicroScalperStateMachine,
    MicroScalperState,
    analisar_micro_scalping,
    executar_replay_ticks,
)
from src.core.motor import Motor


class TestMicroScalperDeterministic(unittest.TestCase):
    """Garante determinismo absoluto e ausência total de random."""

    def test_zero_random_reproducibility(self):
        cat = CatalogadorOtimizado()
        # Série com fundo e reversão
        ticks = [100.0] * 20 + [100.0 - i * 0.4 for i in range(25)] + [90.5, 91.0, 91.5]
        for p in ticks:
            cat.adicionar_tick(p)

        snap = cat.obter_snapshot_mercado("1HZ75V")

        # Executa análise 10 vezes consecutivas
        resultados = [
            analisar_micro_scalping(snap, ultimos_ticks=ticks[-60:])
            for _ in range(10)
        ]

        primeiro = resultados[0]
        for idx, r in enumerate(resultados[1:], 1):
            self.assertEqual(r["sinal"], primeiro["sinal"], f"Divergência de sinal na iteração {idx}")
            self.assertEqual(r["score"], primeiro["score"], f"Divergência de score na iteração {idx}")
            self.assertEqual(r["razao"], primeiro["razao"], f"Divergência de razão na iteração {idx}")
            self.assertEqual(r["confianca"], primeiro["confianca"], f"Divergência de confiança na iteração {idx}")


class TestReversalConfirmation(unittest.TestCase):
    """Garante que o robô NUNCA compre uma queda sem reversão confirmada."""

    def test_no_call_during_free_fall(self):
        cat = CatalogadorOtimizado()
        # Queda livre sem nenhum tick de alta
        ticks = [100.0] * 20 + [100.0 - i * 0.5 for i in range(25)]
        for p in ticks:
            cat.adicionar_tick(p)

        snap = cat.obter_snapshot_mercado("1HZ75V")
        res = analisar_micro_scalping(snap, ultimos_ticks=ticks[-60:])

        # Deve recusar e não emitir sinal CALL
        self.assertIsNone(res["sinal"], "Robô emitiu sinal durante queda livre sem reversão!")
        self.assertIn("Reversão não confirmada", res["motivo_recusa"])

    def test_call_approved_after_bottom_and_reversal(self):
        cat = CatalogadorOtimizado()
        # Queda acentuada até 90.0, seguida de 3 ticks consecutivos de alta com rejeição
        ticks = [100.0] * 30 + [100.0 - i * 0.5 for i in range(20)] + [90.5, 91.0, 91.5]
        for p in ticks:
            cat.adicionar_tick(p)

        snap = cat.obter_snapshot_mercado("1HZ75V")
        res = analisar_micro_scalping(snap, ultimos_ticks=ticks[-60:])

        self.assertEqual(res["sinal"], "CALL", f"Deveria ter confirmado CALL após reversão do fundo: {res}")
        self.assertGreaterEqual(res["score"], 85.0, "Score deve ser >= 85.0 para aprovação")


class TestRiskGateway(unittest.TestCase):
    """Valida as travas invioláveis do Gateway de Risco."""

    def setUp(self):
        self.motor = Motor()
        self.motor.saldo = 100.0
        self.motor.saldo_inicial = 100.0
        self.motor.meta_diaria = 20.0
        self.motor.ultimo_tick_timestamp = time.time()
        self.motor.ultimo_fechamento_ts = 0.0

    def test_blocks_when_position_already_open(self):
        self.motor.operacoes_abertas["fake_contract_1"] = {"id": "fake_contract_1"}
        valido, motivo = self.motor.validar_gateway_risco(0.35)
        self.assertFalse(valido, "Deveria bloquear quando MAX_OPEN_POSITIONS >= 1")
        self.assertIn("Máximo de 1 operação", motivo)

    def test_blocks_during_cooldown(self):
        self.motor.operacoes_abertas = {}
        self.motor.ultimo_fechamento_ts = time.time() - 5.0  # Fechou há 5s (cooldown é 25s)
        valido, motivo = self.motor.validar_gateway_risco(0.35)
        self.assertFalse(valido, "Deveria bloquear durante cooldown pós-operação")
        self.assertIn("cooldown", motivo.lower())

    def test_blocks_when_ticks_are_stale(self):
        self.motor.operacoes_abertas = {}
        self.motor.ultimo_fechamento_ts = time.time() - 60.0
        self.motor.ultimo_tick_timestamp = time.time() - 10.0  # Ticks com 10s de atraso (>2.5s)
        valido, motivo = self.motor.validar_gateway_risco(0.35)
        self.assertFalse(valido, "Deveria bloquear quando ticks estão obsoletos")
        self.assertIn("obsoletos", motivo)

    def test_blocks_when_meta_reached(self):
        self.motor.operacoes_abertas = {}
        self.motor.ultimo_fechamento_ts = time.time() - 60.0
        self.motor.ultimo_tick_timestamp = time.time()
        self.motor.saldo = 125.0  # Lucro de $25 >= Meta de $20
        valido, motivo = self.motor.validar_gateway_risco(0.35)
        self.assertFalse(valido, "Deveria bloquear quando meta diária já foi atingida")
        self.assertIn("Meta diária", motivo)


class TestFirstPositiveProfitExitReplay(unittest.TestCase):
    """Testa o framework determinístico de replay garantindo saída no primeiro lucro líquido."""

    def test_replay_exits_on_first_profit(self):
        # Série controlada com queda até 90.0, virada para 90.5, 91.0, 91.5
        ticks = [100.0] * 30 + [100.0 - i * 0.5 for i in range(20)] + [90.5, 91.0, 91.5, 92.0]
        res = executar_replay_ticks(ticks)

        self.assertGreaterEqual(res["total_operacoes"], 1, "Replay deveria ter operado na reversão do fundo")
        primeira_op = res["historico_operacoes"][0]
        self.assertEqual(primeira_op["motivo_saida"], "FIRST_POSITIVE_PROFIT")
        self.assertGreater(primeira_op["lucro"], 0.0, "Operação deveria ter finalizado com lucro positivo")
        self.assertEqual(res["win_rate_percent"], 100.0)


if __name__ == "__main__":
    unittest.main()
