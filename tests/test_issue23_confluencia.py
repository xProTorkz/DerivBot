# tests/test_issue23_confluencia.py
"""
Testes de Validação da Issue #23:
- Confluência financeira, cálculo de banca, meta e stake derivado
- Idempotência estrita de liquidação
- Regra de 2 perdas consecutivas na sessão
- Parada graciosa manual
- Schema completo de telemetria em /status_robo e persistência de histórico
"""

import json
import time
import unittest
from unittest.mock import MagicMock, patch

from src.config.config import (
    Config,
    PERCENTUAL_META_POR_MODO,
    calcular_meta_sessao,
    calcular_valor_operacao,
    LIMITES_CONCORRENCIA_POR_MODO,
)
from src.core.motor import Motor


class TestIssue23FinancialFormulas(unittest.TestCase):
    """Testa as fórmulas financeiras derivadas de banca e modo de operação (Issue #23.E)."""

    def test_meta_sessao_por_perfil(self):
        saldo = 100.0
        self.assertEqual(calcular_meta_sessao(saldo, "iniciante"), 20.0)
        self.assertEqual(calcular_meta_sessao(saldo, "conservador"), 50.0)
        self.assertEqual(calcular_meta_sessao(saldo, "intermediario"), 50.0)
        self.assertEqual(calcular_meta_sessao(saldo, "agressivo"), 100.0)

    def test_valor_operacao_derivado_com_piso_minimo(self):
        # Meta $20 -> 1% = $0.20 -> piso mínimo de $0.35 da Deriv
        teorico, efetivo, elevado = calcular_valor_operacao(20.0, minimo_contrato=0.35)
        self.assertEqual(teorico, 0.20)
        self.assertEqual(efetivo, 0.35)
        self.assertTrue(elevado)

        # Meta $50 -> 1% = $0.50 -> acima do piso
        teorico_c, efetivo_c, elevado_c = calcular_valor_operacao(50.0, minimo_contrato=0.35)
        self.assertEqual(teorico_c, 0.50)
        self.assertEqual(efetivo_c, 0.50)
        self.assertFalse(elevado_c)

        # Meta $100 -> 1% = $1.00 -> acima do piso
        teorico_a, efetivo_a, elevado_a = calcular_valor_operacao(100.0, minimo_contrato=0.35)
        self.assertEqual(teorico_a, 1.00)
        self.assertEqual(efetivo_a, 1.00)
        self.assertFalse(elevado_a)

    def test_limites_posicoes_rapidas(self):
        self.assertEqual(Config.MAX_OPEN_POSITIONS, 3)
        self.assertEqual(LIMITES_CONCORRENCIA_POR_MODO["iniciante"], 3)


class TestIssue23SettlementIdempotency(unittest.TestCase):
    """Testa a idempotência estrita de liquidações (Issue #23.A)."""

    def setUp(self):
        self.motor = Motor()
        self.motor.ws = MagicMock()
        self.motor.conectado = True
        self.motor.saldo = 1000.0
        self.motor.iniciar_sessao()

    def test_duplicate_settlement_processed_only_once(self):
        contract_id = 99887711
        self.motor.operacoes_abertas[contract_id] = {
            "id": contract_id,
            "contract_id": str(contract_id),
            "ativo": "1HZ10V",
            "preco_entrada": 0.35,
            "valor": 0.35,
            "tipo": "CALL",
            "timestamp_abertura": time.time(),
        }

        msg_sold = {
            "proposal_open_contract": {
                "contract_id": contract_id,
                "profit": 0.32,
                "is_sold": 1,
                "sell_price": 0.67,
                "balance_after": 1000.32,
            }
        }

        # Primeira mensagem de liquidação
        self.motor._on_message(None, json.dumps(msg_sold))
        self.assertEqual(len(self.motor.historico_operacoes), 1)
        self.assertAlmostEqual(self.motor.lucro_realizado_sessao, 0.32)

        # Mensagem repetida (duplicada da stream Deriv)
        self.motor._on_message(None, json.dumps(msg_sold))
        # Deve ter sido ignorada: mesmo tamanho de histórico e lucro inalterado
        self.assertEqual(len(self.motor.historico_operacoes), 1)
        self.assertAlmostEqual(self.motor.lucro_realizado_sessao, 0.32)


class TestIssue23ConsecutiveLossesRule(unittest.TestCase):
    """Testa a regra de 2 perdas consecutivas para parada de sessão (Issue #23.F)."""

    def setUp(self):
        self.motor = Motor()
        self.motor.ws = MagicMock()
        self.motor.conectado = True
        self.motor.saldo = 500.0
        self.motor.iniciar_sessao()  # Inicia sessão com max_perdas_consecutivas = 2

    def test_first_loss_continues_second_loss_stops(self):
        c1 = 11101
        self.motor.operacoes_abertas[c1] = {
            "id": c1,
            "ativo": "1HZ10V",
            "preco_entrada": 0.35,
            "valor": 0.35,
            "tipo": "CALL",
            "timestamp_abertura": time.time(),
        }

        # 1ª perda
        msg_c1 = {
            "proposal_open_contract": {
                "contract_id": c1,
                "profit": -0.35,
                "is_sold": 1,
                "sell_price": 0.0,
                "balance_after": 499.65,
            }
        }
        self.motor._on_message(None, json.dumps(msg_c1))

        # 1ª perda NÃO para a sessão
        self.assertEqual(self.motor.consecutive_losses, 1)
        self.assertFalse(self.motor.session_stopped, "1ª perda deve permitir continuação")

        # 2ª perda
        c2 = 11102
        self.motor.operacoes_abertas[c2] = {
            "id": c2,
            "ativo": "1HZ25V",
            "preco_entrada": 0.35,
            "valor": 0.35,
            "tipo": "PUT",
            "timestamp_abertura": time.time(),
        }
        msg_c2 = {
            "proposal_open_contract": {
                "contract_id": c2,
                "profit": -0.35,
                "is_sold": 1,
                "sell_price": 0.0,
                "balance_after": 499.30,
            }
        }
        self.motor._on_message(None, json.dumps(msg_c2))

        # 2ª perda consecutiva DEVE parar a sessão
        self.assertEqual(self.motor.consecutive_losses, 2)
        self.assertTrue(self.motor.session_stopped, "2 perdas consecutivas devem parar sessão")
        self.assertIn("DUAS_PERDAS_CONSECUTIVAS", self.motor.session_stop_reason)

    def test_win_resets_consecutive_losses_counter(self):
        c1 = 22201
        self.motor.operacoes_abertas[c1] = {
            "id": c1,
            "ativo": "1HZ10V",
            "preco_entrada": 0.35,
            "valor": 0.35,
            "tipo": "CALL",
            "timestamp_abertura": time.time(),
        }
        # 1ª perda
        self.motor._on_message(
            None,
            json.dumps({
                "proposal_open_contract": {
                    "contract_id": c1,
                    "profit": -0.35,
                    "is_sold": 1,
                }
            }),
        )
        self.assertEqual(self.motor.consecutive_losses, 1)

        # Ganho subsequente
        c2 = 22202
        self.motor.operacoes_abertas[c2] = {
            "id": c2,
            "ativo": "1HZ50V",
            "preco_entrada": 0.35,
            "valor": 0.35,
            "tipo": "CALL",
            "timestamp_abertura": time.time(),
        }
        self.motor._on_message(
            None,
            json.dumps({
                "proposal_open_contract": {
                    "contract_id": c2,
                    "profit": 0.32,
                    "is_sold": 1,
                }
            }),
        )
        # Ganho reseta o contador para 0
        self.assertEqual(self.motor.consecutive_losses, 0)
        self.assertFalse(self.motor.session_stopped)


class TestIssue23GracefulManualStop(unittest.TestCase):
    """Testa parada manual graciosa (Issue #23.C / #23.F)."""

    def setUp(self):
        self.motor = Motor()
        self.motor.ws = MagicMock()
        self.motor.conectado = True
        self.motor.saldo = 1000.0
        self.motor.iniciar_sessao()

    def test_graceful_stop_with_active_positions(self):
        c1 = 33301
        self.motor.operacoes_abertas[c1] = {
            "id": c1,
            "ativo": "1HZ10V",
            "preco_entrada": 0.35,
            "valor": 0.35,
            "tipo": "CALL",
            "timestamp_abertura": time.time(),
        }

        # Para motor com contrato aberto
        self.motor.parar()

        # Novas entradas bloqueadas
        self.assertTrue(self.motor.session_stopped)
        self.assertIn("MANUAL_STOP", self.motor.session_stop_reason)
        # O contrato aberto NÃO foi descartado; permanece em operacoes_abertas para saída natural
        self.assertIn(c1, self.motor.operacoes_abertas)


if __name__ == "__main__":
    unittest.main()
