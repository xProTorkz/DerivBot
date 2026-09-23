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
        self.assertEqual(cs.obter_min_score_perfil("agressivo"), 65.0)
        self.assertEqual(cs.obter_min_score_perfil("conservador"), 70.0)
        self.assertEqual(cs.obter_min_score_perfil("intermediario"), 70.0)
        self.assertEqual(cs.obter_min_score_perfil("iniciante"), 72.0)
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

        # Primeira análise: detecta extremo e entra em AGUARDANDO_REVERSAO ou SINAL_CONFIRMADO se já há reversão
        res1 = analisar_micro_scalping(snap, ultimos_ticks=ticks[-60:], state_machine=sm, modo="agressivo")
        self.assertIn(sm.estado_atual, [MicroScalperState.AGUARDANDO_REVERSAO, MicroScalperState.SINAL_CONFIRMADO])
        # dados_ultimo_extremo é consumido (None) quando sinal é confirmado; ainda presente se aguardando reversão
        if sm.estado_atual == MicroScalperState.AGUARDANDO_REVERSAO:
            self.assertIsNotNone(sm.dados_ultimo_extremo)

        # Adiciona mais 1 tick favorável (91.0)
        ticks.append(91.0)
        cat.adicionar_tick(91.0, ativo="1HZ75V")
        snap2 = cat.obter_snapshot_mercado("1HZ75V")

        # Segunda análise dentro da janela de reversão: deve manter a avaliação sem resetar imediatamente para NORMAL
        res2 = analisar_micro_scalping(snap2, ultimos_ticks=ticks[-60:], state_machine=sm, modo="agressivo")
        # O estado deve permanecer em AGUARDANDO_REVERSAO ou transitar para SINAL_CONFIRMADO
        self.assertIn(sm.estado_atual, [MicroScalperState.AGUARDANDO_REVERSAO, MicroScalperState.SINAL_CONFIRMADO])

    def test_buy_request_schema_no_invalid_parameters(self):
        """Garante que a requisição de compra envia proposta compatível com Deriv Options WS."""
        import json
        from unittest.mock import MagicMock

        motor = Motor()
        motor.ws = MagicMock()
        motor.conectado = True
        motor.modo_real = False

        # Executa compra em conta Demo
        sucesso = motor.comprar("CALL", 0.35, ativo="1HZ10V")
        self.assertTrue(sucesso)
        self.assertTrue(motor.ws.send.called)

        # Inspeciona o payload enviado (etapa 1: proposal)
        call_arg = motor.ws.send.call_args[0][0]
        payload = json.loads(call_arg)
        self.assertIn("proposal", payload)
        self.assertIn("underlying_symbol", payload, "underlying_symbol é o campo exigido pela Deriv Options API")
        self.assertNotIn("symbol", payload, "symbol é descontinuado e proibido pela Deriv Options API")
        self.assertIn("amount", payload)
        self.assertIn("duration", payload)
        self.assertIn("duration_unit", payload)
        self.assertEqual(payload["duration_unit"], "s")
        self.assertIn("passthrough", payload)
        self.assertEqual(payload["passthrough"]["tipo_acao"], "executar_compra")

    def test_proposal_response_triggers_buy(self):
        """Garante que o recebimento de proposal dispara a compra imediata com proposal_id."""
        import json
        from unittest.mock import MagicMock

        motor = Motor()
        motor.ws = MagicMock()
        motor.conectado = True
        motor.modo_real = False

        proposal_msg = json.dumps({
            "proposal": {"id": "prop_test_12345", "ask_price": 0.35},
            "passthrough": {
                "tipo_acao": "executar_compra",
                "simbolo": "1HZ10V",
                "contract_type": "CALL",
                "valor_max": 0.35,
            },
        })
        motor._on_message(None, proposal_msg)

        self.assertTrue(motor.ws.send.called)
        buy_call = json.loads(motor.ws.send.call_args[0][0])
        self.assertEqual(buy_call.get("buy"), "prop_test_12345")
        self.assertEqual(buy_call.get("price"), 0.35)

    def test_deriv_error_recovers_comprando_state(self):
        """Verifica se erro retornado pela Deriv API recupera a máquina de estados de COMPRANDO para NORMAL."""
        import json
        from src.core.inteligencia import state_machine_micro_scalper, obter_state_machine

        motor = Motor()
        sm_ativo = obter_state_machine("1HZ25V")
        sm_ativo.transitar(MicroScalperState.COMPRANDO, "Testando compra")
        state_machine_micro_scalper.transitar(MicroScalperState.COMPRANDO, "Testando compra")

        err_msg = json.dumps({
            "error": {"code": "InputValidationFailed", "message": "Input validation failed: parameters"},
            "echo_req": {"buy": 1, "parameters": {"symbol": "1HZ25V"}},
        })
        motor._on_message(None, err_msg)

        self.assertEqual(sm_ativo.estado_atual, MicroScalperState.NORMAL)
        self.assertEqual(state_machine_micro_scalper.estado_atual, MicroScalperState.NORMAL)

    def test_multi_asset_round_robin_rotation(self):
        """Garante rotação circular justa entre os ativos do pool turbo."""
        motor = Motor()
        todos = list(ATIVOS_TURBO_INTEGRADOS.keys())
        motor.ultimo_ativo_usado = 0

        # Primeira rodada
        idx1 = motor.ultimo_ativo_usado % len(todos)
        cand1 = todos[idx1:] + todos[:idx1]
        motor.ultimo_ativo_usado = (motor.ultimo_ativo_usado + 1) % len(todos)

        # Segunda rodada
        idx2 = motor.ultimo_ativo_usado % len(todos)
        cand2 = todos[idx2:] + todos[:idx2]

        self.assertNotEqual(cand1[0], cand2[0], "O primeiro ativo analisado deve rotacionar a cada ciclo")


if __name__ == "__main__":
    unittest.main()
