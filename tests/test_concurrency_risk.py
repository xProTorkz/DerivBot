"""
Suíte de Testes da Concorrência Seletiva 3/5/10 e Session Stop Guard (Issue #20).

Valida:
1. Limites canônicos de concorrência por perfil (Iniciante 3, Intermediário 5, Conservador alias 5, Agressivo 10).
2. Concorrência multi-ativos e múltiplos contratos no mesmo ativo.
3. Cooldown isolado por ativo (sem bloquear ativos concorrentes).
4. Isolamento de estado por contrato/ativo e state machines independentes.
5. Saída FIRST_POSITIVE_PROFIT respeitando sellability (is_valid_to_sell) e timeout.
6. SESSION STOP imediato na primeira perda realizada (lucro <= 0) ou meta atingida.
7. Reconciliação e monitoramento garantido dos contratos remanescentes pós-parada.
8. Trava estrita contra ordens reais (REAL_ORDER_SENT = NO, REAL_ACCOUNT_EXECUTION = BLOCKED).
"""

import time
import json
import unittest
from unittest.mock import MagicMock, patch

from src.config.config import Config, obter_limite_posicoes, normalizar_modo_operacao
from src.core.motor import Motor
from src.core.inteligencia import (
    analisar_micro_scalping,
    obter_state_machine,
    MicroScalperState,
    state_machines_por_ativo,
)


class TestConcurrencyLimitsPerProfile(unittest.TestCase):
    """Testa os limites de concorrência 3 / 5 / 10 e aliases."""

    def test_obter_limite_posicoes(self):
        self.assertEqual(obter_limite_posicoes("iniciante"), 3)
        self.assertEqual(obter_limite_posicoes("intermediario"), 5)
        self.assertEqual(obter_limite_posicoes("conservador"), 5)
        self.assertEqual(obter_limite_posicoes("agressivo"), 10)
        # Defaults
        self.assertEqual(obter_limite_posicoes(None), 3)
        self.assertEqual(obter_limite_posicoes("desconhecido"), 3)

    def test_normalizar_modo_operacao(self):
        self.assertEqual(normalizar_modo_operacao("iniciante"), "iniciante")
        self.assertEqual(normalizar_modo_operacao("conservador"), "intermediario")
        self.assertEqual(normalizar_modo_operacao("intermediario"), "intermediario")
        self.assertEqual(normalizar_modo_operacao("agressivo"), "agressivo")

    def test_iniciante_limit_allows_3_blocks_4(self):
        motor = Motor()
        motor.modo_operacao = "iniciante"
        motor.saldo = 100.0
        motor.saldo_inicial = 100.0
        motor.ultimo_tick_timestamp = time.time()
        motor.ultimo_fechamento_ts = 0.0

        for i in range(3):
            motor.operacoes_abertas[f"c_{i}"] = {"id": f"c_{i}"}
            valido, _ = motor.validar_gateway_risco(0.35)
            if i < 2:
                self.assertTrue(valido, f"Deveria permitir vaga {i+1} de 3")

        # 3 posições abertas já ocupam o limite de 3
        valido, motivo = motor.validar_gateway_risco(0.35)
        self.assertFalse(valido)
        self.assertIn("3", motivo)

    def test_intermediario_limit_allows_5_blocks_6(self):
        motor = Motor()
        motor.modo_operacao = "intermediario"
        motor.saldo = 100.0
        motor.saldo_inicial = 100.0
        motor.ultimo_tick_timestamp = time.time()
        motor.ultimo_fechamento_ts = 0.0

        for i in range(4):
            motor.operacoes_abertas[f"c_{i}"] = {"id": f"c_{i}"}

        # Com 4 abertas, 5ª ainda é permitida
        valido, _ = motor.validar_gateway_risco(0.35)
        self.assertTrue(valido, "Deveria permitir 5ª vaga para intermediario")

        motor.operacoes_abertas["c_4"] = {"id": "c_4"}
        # Com 5 abertas, 6ª é bloqueada
        valido, motivo = motor.validar_gateway_risco(0.35)
        self.assertFalse(valido)
        self.assertIn("5", motivo)

    def test_conservador_alias_treats_as_5(self):
        motor = Motor()
        motor.modo_operacao = "conservador"
        motor.saldo = 100.0
        motor.saldo_inicial = 100.0
        motor.ultimo_tick_timestamp = time.time()
        motor.ultimo_fechamento_ts = 0.0

        for i in range(5):
            motor.operacoes_abertas[f"c_{i}"] = {"id": f"c_{i}"}

        valido, motivo = motor.validar_gateway_risco(0.35)
        self.assertFalse(valido)
        self.assertIn("5", motivo)

    def test_agressivo_limit_allows_10_blocks_11(self):
        motor = Motor()
        motor.modo_operacao = "agressivo"
        motor.saldo = 200.0
        motor.saldo_inicial = 200.0
        motor.ultimo_tick_timestamp = time.time()
        motor.ultimo_fechamento_ts = 0.0

        for i in range(9):
            motor.operacoes_abertas[f"c_{i}"] = {"id": f"c_{i}"}

        # 10ª posição permitida
        valido, _ = motor.validar_gateway_risco(0.35)
        self.assertTrue(valido, "Deveria permitir 10ª vaga para agressivo")

        motor.operacoes_abertas["c_9"] = {"id": "c_9"}
        # 11ª bloqueada
        valido, motivo = motor.validar_gateway_risco(0.35)
        self.assertFalse(valido)
        self.assertIn("10", motivo)


class TestMultiAssetAndCooldownIsolation(unittest.TestCase):
    """Testa múltiplos ativos e isolamento de cooldown."""

    def setUp(self):
        self.motor = Motor()
        self.motor.modo_operacao = "agressivo"
        self.motor.saldo = 200.0
        self.motor.saldo_inicial = 200.0
        self.motor.ultimo_tick_timestamp = time.time()
        self.motor.ultimo_fechamento_ts = 0.0
        self.motor.cooldowns_por_ativo = {}

    def test_allows_different_assets_simultaneously(self):
        self.motor.operacoes_abertas["c_vix75"] = {"id": "c_vix75", "ativo": "1HZ75V"}
        self.motor.operacoes_abertas["c_vix100"] = {"id": "c_vix100", "ativo": "1HZ100V"}
        self.motor.operacoes_abertas["c_r10"] = {"id": "c_r10", "ativo": "R_10"}

        valido, _ = self.motor.validar_gateway_risco(0.35, ativo="R_25")
        self.assertTrue(valido, "Deveria permitir abertura em novo ativo dentro do limite")

    def test_allows_same_asset_distinct_contracts(self):
        self.motor.operacoes_abertas["c_vix75_1"] = {"id": "c_vix75_1", "ativo": "1HZ75V"}
        # Novo contrato no mesmo ativo 1HZ75V é permitido desde que não em cooldown e com vagas
        valido, _ = self.motor.validar_gateway_risco(0.35, ativo="1HZ75V")
        self.assertTrue(valido, "Deveria permitir novo contrato no mesmo ativo se houver vaga")

    def test_asset_cooldown_does_not_block_other_assets(self):
        # 1HZ75V fechou há 2 segundos (cooldown é 25s)
        self.motor.cooldowns_por_ativo["1HZ75V"] = time.time() - 2.0

        # Checagem em 1HZ75V deve bloquear
        valido_75, motivo_75 = self.motor.validar_gateway_risco(0.35, ativo="1HZ75V")
        self.assertFalse(valido_75)
        self.assertIn("1HZ75V", motivo_75)
        self.assertIn("cooldown", motivo_75.lower())

        # Checagem em 1HZ100V NÃO deve bloquear
        valido_100, _ = self.motor.validar_gateway_risco(0.35, ativo="1HZ100V")
        self.assertTrue(valido_100, "Cooldown de 1HZ75V não deve afetar 1HZ100V")

        # Checagem em R_10 NÃO deve bloquear
        valido_r10, _ = self.motor.validar_gateway_risco(0.35, ativo="R_10")
        self.assertTrue(valido_r10, "Cooldown de 1HZ75V não deve afetar R_10")


class TestStateMachineIsolation(unittest.TestCase):
    """Testa o isolamento de state machines por ativo."""

    def setUp(self):
        state_machines_por_ativo.clear()

    def test_state_machines_are_isolated(self):
        sm_vix75 = obter_state_machine("1HZ75V")
        sm_vix100 = obter_state_machine("1HZ100V")

        self.assertIsNot(sm_vix75, sm_vix100)

        sm_vix75.transitar(MicroScalperState.EXTREMO_DETECTADO, "Extremo em VIX75")
        self.assertEqual(sm_vix75.estado_atual, MicroScalperState.EXTREMO_DETECTADO)
        self.assertEqual(sm_vix100.estado_atual, MicroScalperState.NORMAL)


class TestFirstPositiveProfitAndSellability(unittest.TestCase):
    """Testa saída no primeiro lucro líquido respeitando is_valid_to_sell."""

    def setUp(self):
        self.motor = Motor()
        self.motor.ws = MagicMock()
        self.motor.conectado = True
        self.motor.par_atual = "1HZ75V"
        self.motor.fechar_operacao = MagicMock()

    def test_sells_only_when_valid_to_sell(self):
        contract_id = 99901
        self.motor.operacoes_abertas[contract_id] = {
            "id": contract_id,
            "ativo": "1HZ75V",
            "timestamp_abertura": time.time(),
            "positive_updates": 1,
            "motivo_saida": "",
        }

        # Mensagem com lucro positivo mas is_valid_to_sell == 0
        msg_not_sellable = {
            "proposal_open_contract": {
                "contract_id": contract_id,
                "profit": 0.05,
                "is_sold": 0,
                "is_valid_to_sell": 0,
            }
        }
        self.motor._on_message(None, json.dumps(msg_not_sellable))
        self.motor.fechar_operacao.assert_not_called()
        self.assertEqual(self.motor.operacoes_abertas[contract_id]["positive_updates"], 2)

        # Mensagem subsequente com is_valid_to_sell == 1
        msg_sellable = {
            "proposal_open_contract": {
                "contract_id": contract_id,
                "profit": 0.05,
                "is_sold": 0,
                "is_valid_to_sell": 1,
            }
        }
        self.motor._on_message(None, json.dumps(msg_sellable))
        self.motor.fechar_operacao.assert_called_once_with(contract_id)
        self.assertEqual(
            self.motor.operacoes_abertas[contract_id]["motivo_saida"],
            "FIRST_POSITIVE_PROFIT",
        )

    def test_max_hold_timeout_exits_when_sellable(self):
        contract_id = 99902
        self.motor.operacoes_abertas[contract_id] = {
            "id": contract_id,
            "ativo": "1HZ75V",
            "timestamp_abertura": time.time() - 50.0,  # 50s atrás (> 45s max_hold)
            "positive_updates": 0,
            "motivo_saida": "",
        }

        msg = {
            "proposal_open_contract": {
                "contract_id": contract_id,
                "profit": -0.01,
                "is_sold": 0,
                "is_valid_to_sell": 1,
            }
        }
        self.motor._on_message(None, json.dumps(msg))
        self.motor.fechar_operacao.assert_called_once_with(contract_id)
        self.assertEqual(
            self.motor.operacoes_abertas[contract_id]["motivo_saida"],
            "MAX_HOLD_TIMEOUT",
        )


class TestSessionStopGuard(unittest.TestCase):
    """Testa a parada de sessão (SESSION STOP) por meta ou primeira perda realizada."""

    def setUp(self):
        self.motor = Motor()
        self.motor.ws = MagicMock()
        self.motor.conectado = True
        self.motor.saldo = 100.0
        self.motor.saldo_inicial = 100.0
        self.motor.meta_diaria = 20.0
        self.motor.modo_operacao = "iniciante"
        self.motor.max_perdas_consecutivas = 1

    def test_session_stops_on_first_loss(self):
        contract_id = 88801
        self.motor.operacoes_abertas[contract_id] = {
            "id": contract_id,
            "ativo": "1HZ75V",
            "timestamp_abertura": time.time() - 10.0,
            "tipo": "CALL",
            "valor": 0.35,
        }

        # Contrato encerra com perda de $0.35 (profit <= 0)
        msg_sold_loss = {
            "proposal_open_contract": {
                "contract_id": contract_id,
                "profit": -0.35,
                "is_sold": 1,
                "sell_price": 0.0,
                "balance_after": 99.65,
            }
        }
        self.motor._on_message(None, json.dumps(msg_sold_loss))

        self.assertTrue(self.motor.session_stopped, "Deveria parar sessão na primeira perda")
        self.assertIn("PRIMEIRA_PERDA_REALIZADA", self.motor.session_stop_reason)

        # Nova verificação no gateway de risco deve ser barrada imediatamente
        valido, motivo = self.motor.validar_gateway_risco(0.35)
        self.assertFalse(valido)
        self.assertIn("Sessão parada", motivo)

    def test_session_stops_on_zero_profit(self):
        contract_id = 88802
        self.motor.operacoes_abertas[contract_id] = {
            "id": contract_id,
            "ativo": "1HZ100V",
            "timestamp_abertura": time.time() - 10.0,
            "tipo": "PUT",
            "valor": 0.35,
        }

        # Contrato encerra com lucro 0.00 (profit <= 0)
        msg_sold_zero = {
            "proposal_open_contract": {
                "contract_id": contract_id,
                "profit": 0.00,
                "is_sold": 1,
                "sell_price": 0.35,
                "balance_after": 100.0,
            }
        }
        self.motor._on_message(None, json.dumps(msg_sold_zero))

        self.assertTrue(self.motor.session_stopped, "Deveria parar sessão quando lucro <= 0")
        self.assertIn("PRIMEIRA_PERDA_REALIZADA", self.motor.session_stop_reason)

    def test_session_stops_on_meta_reached(self):
        contract_id = 88803
        self.motor.operacoes_abertas[contract_id] = {
            "id": contract_id,
            "ativo": "1HZ75V",
            "timestamp_abertura": time.time() - 10.0,
            "tipo": "CALL",
            "valor": 0.35,
        }

        # Lucro atinge a meta
        msg_sold_win = {
            "proposal_open_contract": {
                "contract_id": contract_id,
                "profit": 20.50,
                "is_sold": 1,
                "sell_price": 20.85,
                "balance_after": 120.50,
            }
        }
        self.motor._on_message(None, json.dumps(msg_sold_win))

        self.assertTrue(self.motor.session_stopped, "Deveria parar sessão com meta atingida")
        self.assertIn("META_ATINGIDA", self.motor.session_stop_reason)
        self.assertTrue(self.motor.meta_atingida)

    def test_reconciliation_keeps_monitoring_remaining_contracts(self):
        """Quando sessão é parada, contratos abertos restantes não são abandonados."""
        c1 = 77701
        c2 = 77702

        self.motor.operacoes_abertas[c1] = {
            "id": c1,
            "ativo": "1HZ75V",
            "timestamp_abertura": time.time(),
            "tipo": "CALL",
            "valor": 0.35,
        }
        self.motor.operacoes_abertas[c2] = {
            "id": c2,
            "ativo": "1HZ100V",
            "timestamp_abertura": time.time(),
            "tipo": "PUT",
            "valor": 0.35,
        }

        # c1 encerra com perda -> dispara SESSION STOP
        msg_c1 = {
            "proposal_open_contract": {
                "contract_id": c1,
                "profit": -0.35,
                "is_sold": 1,
                "sell_price": 0.0,
                "balance_after": 99.65,
            }
        }
        self.motor._on_message(None, json.dumps(msg_c1))

        self.assertTrue(self.motor.session_stopped)
        # c2 ainda está aberto e sendo monitorado!
        self.assertIn(c2, self.motor.operacoes_abertas)
        self.assertEqual(len(self.motor.operacoes_abertas), 1)

        # Atualizações para c2 continuam sendo processadas normalmente
        msg_c2_update = {
            "proposal_open_contract": {
                "contract_id": c2,
                "profit": 0.04,
                "is_sold": 0,
                "is_valid_to_sell": 1,
            }
        }
        self.motor.fechar_operacao = MagicMock()
        self.motor.operacoes_abertas[c2]["positive_updates"] = 2
        self.motor._on_message(None, json.dumps(msg_c2_update))
        self.motor.fechar_operacao.assert_called_once_with(c2)


class TestRealAccountStrictSafetyLock(unittest.TestCase):
    """Testa trava rígida contra ordens em conta REAL."""

    def test_comprar_blocks_in_real_mode(self):
        motor = Motor()
        motor.ws = MagicMock()
        motor.conectado = True
        motor.modo_real = True  # Conta REAL

        sucesso = motor.comprar("CALL", 0.35, ativo="1HZ75V")
        self.assertFalse(sucesso, "Deveria bloquear execução de compra em conta REAL")
        motor.ws.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
