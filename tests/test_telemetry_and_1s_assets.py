"""
Testes automatizados para os ativos de 1 segundo (VIX 1s),
persistência da janela de reversão e calibração de score por perfil.
"""

import os
import sys
import time
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.core.catalogador import ATIVOS_TURBO_INTEGRADOS, CatalogadorOtimizado
from src.core.inteligencia import (
    ConfluenceScore,
    MicroScalperState,
    MicroScalperStateMachine,
    analisar_micro_scalping,
)
from src.core.motor import Motor


class TestOneSecondAssetsAndPersistence(unittest.TestCase):
    """Garante suporte completo aos ativos de 1 segundo e janela de reversão."""

    def test_one_second_assets_integrated(self):
        """Verifica se todos os 5 ativos de 1 segundo estão em ATIVOS_TURBO_INTEGRADOS."""
        ativos_1s = ["1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V"]
        for ativo in ativos_1s:
            self.assertIn(ativo, ATIVOS_TURBO_INTEGRADOS, f"Ativo {ativo} ausente em ATIVOS_TURBO_INTEGRADOS")
            cfg = ATIVOS_TURBO_INTEGRADOS[ativo]
            self.assertEqual(cfg["tipo_contrato"], "turbo")
            self.assertEqual(cfg["duracao_segundos"], 15)
            self.assertEqual(cfg["min_stake"], 0.35)

    def test_motor_monitors_one_second_assets(self):
        """Verifica se o motor monitora os ativos de 1 segundo prioritariamente."""
        motor = Motor()
        ativos_1s = ["1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V"]
        for ativo in ativos_1s:
            self.assertIn(ativo, motor.ativos_ativos, f"Ativo {ativo} não está na lista de monitoramento do motor")

    def test_score_calibration_by_profile(self):
        """Verifica calibração dinâmica do score mínimo por perfil de risco."""
        cs = ConfluenceScore()
        self.assertEqual(cs.obter_min_score_perfil("agressivo"), 70.0)
        self.assertEqual(cs.obter_min_score_perfil("conservador"), 78.0)
        self.assertEqual(cs.obter_min_score_perfil("intermediario"), 78.0)
        self.assertEqual(cs.obter_min_score_perfil("iniciante"), 82.0)
        # Sem perfil especificado mantém padrão (85.0)
        self.assertEqual(cs.obter_min_score_perfil(None), 85.0)

    def test_reversal_window_holds_waiting_state(self):
        """Garante que a máquina de estados sustenta AGUARDANDO_REVERSAO durante a janela de tolerância."""
        cat = CatalogadorOtimizado()
        # Série com fundo e início de reversão
        ticks = [100.0] * 30 + [100.0 - i * 0.5 for i in range(20)] + [90.5]
        for p in ticks:
            cat.adicionar_tick(p, ativo="1HZ75V")

        snap = cat.obter_snapshot_mercado("1HZ75V")
        sm = MicroScalperStateMachine()

        # Primeira análise: detecta extremo e entra em AGUARDANDO_REVERSAO
        res1 = analisar_micro_scalping(snap, ultimos_ticks=ticks[-60:], state_machine=sm, modo="agressivo")
        self.assertEqual(sm.estado_atual, MicroScalperState.AGUARDANDO_REVERSAO)
        self.assertIsNotNone(sm.dados_ultimo_extremo)

        # Adiciona mais 1 tick favorável (91.0)
        ticks.append(91.0)
        cat.adicionar_tick(91.0, ativo="1HZ75V")
        snap2 = cat.obter_snapshot_mercado("1HZ75V")

        # Segunda análise dentro da janela de reversão: deve manter a avaliação sem resetar imediatamente para NORMAL
        res2 = analisar_micro_scalping(snap2, ultimos_ticks=ticks[-60:], state_machine=sm, modo="agressivo")
        # O estado deve permanecer em AGUARDANDO_REVERSAO ou transitar para SINAL_CONFIRMADO
        self.assertIn(sm.estado_atual, [MicroScalperState.AGUARDANDO_REVERSAO, MicroScalperState.SINAL_CONFIRMADO])


if __name__ == "__main__":
    unittest.main()
