"""
Testes do Ciclo de Vida da Sessão, Sincronização do /status_robo e Funil de 7 Estágios.
"""

import time
import json
import unittest
from unittest.mock import MagicMock, patch

from src.core.motor import Motor
from src.core.inteligencia import MicroScalperState


class TestSessionLifecycle(unittest.TestCase):
    """Valida o reset do ciclo de vida da sessão e eliminação do falso ativo."""

    def setUp(self):
        self.motor = Motor()
        self.motor.saldo = 1000.0
        self.motor.saldo_inicial = 1000.0
        self.motor.ultimo_tick_timestamp = time.time()

    def test_iniciar_sessao_resets_stopped_state(self):
        """Garante que iniciar_sessao limpa session_stopped e zera acumuladores."""
        # Simula uma sessão anterior parada por perda ou meta
        self.motor.session_stopped = True
        self.motor.session_stop_reason = "PRIMEIRA_PERDA_REALIZADA"
        self.motor.lucro_acumulado_sessao = -0.35
        self.motor.rodando = False
        self.motor.contadores_funil["BUY_CONFIRMED"] = 5

        # Gateway de risco deve bloquear enquanto session_stopped for True
        valido, motivo = self.motor.validar_gateway_risco(0.35)
        self.assertFalse(valido)
        self.assertIn("Sessão parada", motivo)

        # Inicia nova sessão
        self.motor.iniciar_sessao()

        # Verifica reset completo
        self.assertFalse(self.motor.session_stopped)
        self.assertIsNone(self.motor.session_stop_reason)
        self.assertEqual(self.motor.lucro_acumulado_sessao, 0.0)
        self.assertEqual(self.motor.saldo_inicial, 1000.0)
        self.assertTrue(self.motor.rodando)
        self.assertEqual(self.motor.ultimo_estagio_execucao, "INICIANDO")
        self.assertEqual(self.motor.contadores_funil["BUY_CONFIRMED"], 0)

        # Gateway de risco agora deve aprovar
        valido, _ = self.motor.validar_gateway_risco(0.35)
        self.assertTrue(valido)

    def test_parar_sets_session_stopped_and_reason(self):
        """Garante que parar() registra razão e finaliza formalmente."""
        self.motor.iniciar_sessao()
        self.assertTrue(self.motor.rodando)

        self.motor.parar()

        self.assertFalse(self.motor.rodando)
        self.assertTrue(self.motor.session_stopped)
        self.assertIn("MANUAL_STOP", self.motor.session_stop_reason)
        self.assertEqual(self.motor.ultimo_estagio_execucao, "PARADO")

    def test_funnel_counters_incrementation(self):
        """Garante que os contadores do funil são incrementados nos estágios corretos."""
        self.motor.iniciar_sessao()
        self.assertEqual(self.motor.contadores_funil["SCAN"], 0)

        # Simula passagem por SCAN
        self.motor.executar_operacao_inteligente()
        self.assertGreaterEqual(self.motor.contadores_funil["SCAN"], 1)

        # Simula resposta de proposal
        data_proposal = {
            "proposal": {
                "id": "prop_test_999",
                "ask_price": 0.35,
                "payout": 0.68,
            },
            "passthrough": {
                "tipo_acao": "executar_compra",
                "simbolo": "1HZ10V",
                "valor_max": 0.35,
            }
        }
        self.motor.ws = MagicMock()
        self.motor._on_message(None, json.dumps(data_proposal))
        self.assertEqual(self.motor.contadores_funil["PROPOSAL_RECEIVED"], 1)
        self.assertEqual(self.motor.contadores_funil["BUY_SENT"], 1)

        # Simula confirmação de buy
        data_buy = {
            "buy": {
                "contract_id": 999888777,
                "buy_price": 0.35,
            },
            "passthrough": {
                "simbolo": "1HZ10V",
                "contract_type": "CALL",
                "transaction_id": "tx_test_1",
            }
        }
        self.motor._on_message(None, json.dumps(data_buy))
        self.assertEqual(self.motor.contadores_funil["BUY_CONFIRMED"], 1)
        self.assertEqual(self.motor.ultimo_estagio_execucao, "BUY_CONFIRMED")

    def test_error_sets_ultimo_erro_deriv(self):
        """Garante que erros da API Deriv são armazenados em ultimo_erro_deriv."""
        self.motor.iniciar_sessao()
        data_error = {
            "error": {
                "code": "InvalidContractProposal",
                "message": "The proposed contract is not available",
            },
            "echo_req": {"buy": 1}
        }
        self.motor._on_message(None, json.dumps(data_error))
        self.assertIsNotNone(self.motor.ultimo_erro_deriv)
        self.assertIn("InvalidContractProposal", self.motor.ultimo_erro_deriv)


class TestStatusRoboEndpoint(unittest.TestCase):
    """Valida que /status_robo nunca devolve falso positivo de ativo."""

    @patch("src.main.motor")
    def test_status_robo_reflects_stopped_motor(self, mock_motor):
        from src import main
        mock_motor.rodando = False
        mock_motor.session_stopped = True
        mock_motor.session_stop_reason = "PRIMEIRA_PERDA_REALIZADA"
        mock_motor.ultimo_erro_deriv = None
        mock_motor.ultimo_estagio_execucao = "PARADO"
        mock_motor.contadores_funil = {"SCAN": 10, "SIGNAL": 0}
        mock_motor.par_atual = "1HZ75V"
        mock_motor.saldo = 1000.0
        mock_motor.operacoes_abertas = {}
        mock_motor.ultima_telemetria_analise = {}
        mock_motor.ultimo_motivo_recusa = ""
        mock_motor.ultimo_score = 0.0
        mock_motor.conectado = True
        mock_motor.ultimo_erro = None

        # Mesmo se global robo_ativo fosse True:
        main.robo_ativo = True

        with main.app.test_client() as client:
            with client.session_transaction() as sess:
                sess["token"] = "valid_token"
                sess["tipo_conta"] = "demo"

            res = client.get("/status_robo")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()

            # O endpoint DEVE retornar ativo = False
            self.assertFalse(data["ativo"])
            self.assertFalse(data["motor_rodando"])
            self.assertTrue(data["session_stopped"])
            self.assertEqual(data["session_stop_reason"], "PRIMEIRA_PERDA_REALIZADA")
            self.assertEqual(data["contadores_funil"]["SCAN"], 10)

            # E robo_ativo global deve ter sido sincronizado para False
            self.assertFalse(main.robo_ativo)
