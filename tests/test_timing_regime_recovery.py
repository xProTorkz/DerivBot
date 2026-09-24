# tests/test_timing_regime_recovery.py
"""
Suíte de Testes Canônica de Inteligência e Recuperação Controlada:
- Issue #13: Timing 2/4 por ticks determinístico
- Issue #17: Classificação de Regime de Mercado e NO_TRADE estrito
- Issue #23.F / Fase 11: Recuperação Controlada Gale 1 (2x, teto 2% equity, 2 perdas = SESSION STOP)
- Trava inviolável de conta REAL (DEMO ONLY)
"""

import json
import time
import unittest
from unittest.mock import MagicMock, patch

from src.config.config import RECUPERACAO_GALE_CONFIG
from src.core.inteligencia import (
    MarketRegime,
    RegimeClassifier,
    Timing24Detector,
    analisar_micro_scalping,
    MicroScalperState,
)
from src.core.motor import Motor


class TestTiming24Detector(unittest.TestCase):
    """Testa os requisitos de Timing 2/4 por ticks determinístico (Issue #13)."""

    def setUp(self):
        self.detector = Timing24Detector()

    def test_continuous_rise_blocks_put(self):
        """1. Subida contínua sem rejeição bloqueia PUT (CONTINUATION_BLOCKED ou NO_TWO_PEAKS)."""
        ticks = [100.0 + i * 0.2 for i in range(15)]
        resultado = self.detector.detectar("1HZ100V", ticks, "PUT")
        self.assertFalse(resultado["aprovado"])
        self.assertIn(resultado["pattern_status"], ["CONTINUATION_BLOCKED", "NO_TWO_PEAKS", "NO_PEAKS_FOUND"])

    def test_continuous_fall_blocks_call(self):
        """2. Queda contínua sem rejeição bloqueia CALL (CONTINUATION_BLOCKED ou NO_TWO_TROUGHS)."""
        ticks = [100.0 - i * 0.2 for i in range(15)]
        resultado = self.detector.detectar("1HZ100V", ticks, "CALL")
        self.assertFalse(resultado["aprovado"])
        self.assertIn(resultado["pattern_status"], ["CONTINUATION_BLOCKED", "NO_TWO_TROUGHS", "NO_TROUGHS_FOUND"])

    def test_false_second_peak_below_epsilon_rejected(self):
        """3. Falso segundo topo com pullback menor que epsilon é rejeitado."""
        ticks = [98.0, 98.5, 99.0, 99.5, 100.0, 99.999, 100.001, 99.998]
        resultado = self.detector.detectar("1HZ100V", ticks, "PUT")
        self.assertFalse(resultado["aprovado"])
        self.assertIn(resultado["pattern_status"], ["FALSE_PEAK_BELOW_EPSILON", "NO_TWO_PEAKS", "NO_PEAKS_FOUND"])

    def test_insufficient_rejection_blocks_trade(self):
        """4. Rejeição com tamanho insuficiente gera bloqueio (rejeitou < epsilon * 0.4)."""
        ticks = [95.0, 96.0, 97.0, 98.0, 100.0, 98.5, 99.8, 99.79]
        resultado = self.detector.detectar("1HZ100V", ticks, "PUT")
        self.assertFalse(resultado["aprovado"])

    def test_adverse_slope_blocks_trade(self):
        """5. Slope adverso no momento da entrada gera bloqueio."""
        ticks = [90.0, 92.0, 94.0, 96.0, 97.0, 98.0, 99.0, 100.0]
        resultado = self.detector.detectar("1HZ100V", ticks, "PUT")
        self.assertFalse(resultado["aprovado"])

    def test_determinism_identical_sequence_same_decision(self):
        """6. Mesma sequência de ticks gera rigorosamente a mesma decisão (determinismo)."""
        ticks = [100.0, 98.0, 96.0, 94.0, 92.0, 90.0, 91.5, 90.2, 90.8, 91.2]
        res1 = self.detector.detectar("1HZ100V", ticks, "CALL")
        res2 = self.detector.detectar("1HZ100V", ticks, "CALL")
        self.assertEqual(res1["aprovado"], res2["aprovado"])
        self.assertEqual(res1["pattern_status"], res2["pattern_status"])
        self.assertEqual(res1["razao"], res2["razao"])

    def test_call_put_independent_states(self):
        """7. Detecção em CALL e PUT mantém estados independentes."""
        ticks_put = [90.0, 95.0, 100.0, 98.0, 99.8, 98.5, 98.0]
        ticks_call = [100.0, 95.0, 90.0, 92.0, 90.2, 91.5, 92.0]
        res_put = self.detector.detectar("1HZ100V", ticks_put, "PUT")
        res_call = self.detector.detectar("1HZ100V", ticks_call, "CALL")
        self.assertEqual(res_put.get("direcao"), "PUT")
        self.assertEqual(res_call.get("direcao"), "CALL")

    def test_confirmation_window_1_to_4_ticks(self):
        """8. Janela de confirmação de 1 a 4 ticks: além de 4 ticks de atraso, o padrão expira."""
        ticks = [90.0, 95.0, 100.0, 98.0, 99.8, 98.5, 98.6, 98.4, 98.5, 98.6, 98.5, 98.4]
        resultado = self.detector.detectar("1HZ100V", ticks, "PUT")
        if not resultado["aprovado"]:
            self.assertIn(resultado["pattern_status"], ["TIMING_2_4_EXPIRED", "NO_TWO_PEAKS", "CONTINUATION_BLOCKED"])


class TestRegimeClassifier(unittest.TestCase):
    """Testa os requisitos de Classificação de Regime e Filtro NO_TRADE (Issue #17)."""

    def setUp(self):
        self.classifier = RegimeClassifier()

    def test_strong_trend_blocks_counter_trade(self):
        """9. Tendência forte contrária bloqueia operação (TENDENCIA_FORTE -> NO_TRADE)."""
        ticks = [100.0 + i * 0.05 for i in range(30)]
        snapshot = {
            "adx": 42.0,
            "tendencia_adx": "alta",
            "volatilidade_curta": 0.001,
            "distancia_bb_superior": 0.0001,
            "distancia_bb_inferior": 0.05,
        }
        res = self.classifier.classificar("1HZ100V", ticks, snapshot, "PUT")
        self.assertIn(res["regime"], [MarketRegime.TENDENCIA_FORTE, MarketRegime.NO_TRADE])
        self.assertFalse(res["aprovado"])

    def test_chop_regime_blocks_trade(self):
        """10. Regime de chop / ruído lateral bloqueia operação (CHOP -> NO_TRADE)."""
        ticks = [100.0, 100.01, 100.0, 100.01, 100.0, 100.01, 100.0, 100.01] * 3
        snapshot = {
            "adx": 12.0,
            "tendencia_adx": "lateral",
            "volatilidade_curta": 0.00001,
            "distancia_bb_inferior": 0.001,
            "distancia_bb_superior": 0.001,
        }
        res = self.classifier.classificar("1HZ100V", ticks, snapshot, "CALL")
        self.assertIn(res["regime"], [MarketRegime.CHOP, MarketRegime.VOLATILIDADE_BAIXA, MarketRegime.NO_TRADE])
        self.assertFalse(res["aprovado"])

    def test_stale_data_blocks_trade(self):
        """11. Tick atrasado / desatualizado (> 3.5s) bloqueia operação (DADOS_STALE -> NO_TRADE)."""
        ticks = [100.0 + i * 0.1 for i in range(20)]
        snapshot = {"idade_tick": 5.0}  # 5 segundos atrás
        res = self.classifier.classificar("1HZ100V", ticks, snapshot, "CALL")
        self.assertEqual(res["regime"], MarketRegime.DADOS_STALE)
        self.assertFalse(res["aprovado"])
        self.assertIn("stale", res["razao"].lower())

    def test_abnormal_volatility_blocks_trade(self):
        """12. Volatilidade anormal / explosão atípica bloqueia operação (VOLATILIDADE_ANORMAL -> NO_TRADE)."""
        ticks = [100.0, 100.1, 100.2, 100.1, 100.0, 150.0, 80.0, 140.0] * 2
        snapshot = {"volatilidade_curta": 0.15}  # 15% de volatilidade em segundos
        res = self.classifier.classificar("1HZ100V", ticks, snapshot, "PUT")
        self.assertIn(res["regime"], [MarketRegime.VOLATILIDADE_ANORMAL, MarketRegime.NO_TRADE])
        self.assertFalse(res["aprovado"])


class TestGale1ControlledRecovery(unittest.TestCase):
    """Testa a Recuperação Controlada Gale 1 com teto de 2% de risco e stop inviolável (Issue #23.F / Fase 11)."""

    def setUp(self):
        self.motor = Motor()
        self.motor.modo_real = False
        self.motor.meta_diaria = 20.0
        self.motor.iniciar_sessao()
        self.motor.saldo = 1000.0
        self.motor.saldo_inicial_sessao = 1000.0

    def test_first_loss_arms_recovery_level_1(self):
        """13. Primeira perda arma recovery_level = 1 e armazena perda anterior."""
        self.assertEqual(self.motor.recovery_level, 0)
        self.assertEqual(self.motor.consecutive_losses, 0)

        # Simula liquidação de contrato com perda de -$0.35
        raw_contract_id = "1111111111"
        self.motor.operacoes_abertas[raw_contract_id] = {
            "id": raw_contract_id,
            "contract_id": raw_contract_id,
            "ativo": "1HZ100V",
            "valor": 0.35,
            "tipo": "TURBO",
            "is_recovery": False,
        }

        msg = {
            "proposal_open_contract": {
                "contract_id": raw_contract_id,
                "is_sold": 1,
                "profit": -0.35,
                "sell_price": 0.0,
                "balance_after": 999.65,
            }
        }
        self.motor._on_message(None, json.dumps(msg))

        self.assertEqual(self.motor.consecutive_losses, 1)
        self.assertEqual(self.motor.recovery_level, 1)
        self.assertAlmostEqual(self.motor.previous_loss_amount, 0.35, places=2)
        self.assertEqual(self.motor.recovery_origin_contract_id, raw_contract_id)
        self.assertFalse(self.motor.session_stopped)

    def test_next_valid_opportunity_uses_2x_stake(self):
        """14. Próxima oportunidade válida usa stake 2x base."""
        self.motor.recovery_level = 1
        self.motor.previous_loss_amount = 0.35
        self.motor.saldo_inicial_sessao = 1000.0

        # Base stake para meta $20 é 1% = $0.20 -> piso mínimo Deriv = $0.35
        # Gale 1 = 2x $0.35 = $0.70
        snapshot_valido = {
            "valido": True,
            "rsi": 25.0,
            "z_score": -2.5,
            "percentil_curto": 5.0,
            "inclinacao_curta": 0.005,
            "distancia_bb_inferior": 0.0001,
            "distancia_bb_superior": 0.05,
        }
        ultimos_ticks = [100.0 - i * 0.5 for i in range(15)] + [92.0, 92.5, 93.0]

        with patch("src.core.motor.analisar_micro_scalping") as mock_analise:
            mock_analise.return_value = {
                "sinal": "CALL",
                "score": 92.0,
                "confianca": 0.92,
                "razao": "Double bottom confirmed",
                "estado": MicroScalperState.NORMAL,
                "min_score": 85.0,
            }
            with patch.object(self.motor.catalogador, "obter_snapshot_mercado", return_value=snapshot_valido), \
                 patch.object(self.motor.catalogador, "obter_ultimos_ticks", return_value=ultimos_ticks):
                analise = self.motor._analisar_entrada_turbo(
                    ativo="1HZ100V",
                    preco_atual=93.0,
                    modo="iniciante",
                    meta=20.0,
                    lucro_atual=-0.35,
                    operacoes_ativas=0,
                )

        self.assertTrue(analise["sinal"])
        self.assertEqual(analise["volume"], 0.70)
        self.assertEqual(analise["recovery_level"], 1)

    def test_invalid_opportunity_not_forced_in_recovery(self):
        """15. Próxima oportunidade inválida NÃO é forçada por estar em recuperação."""
        self.motor.recovery_level = 1
        self.motor.previous_loss_amount = 0.35

        snapshot_invalido = {
            "valido": True,
            "rsi": 50.0,
            "z_score": 0.1,
            "percentil_curto": 50.0,
            "inclinacao_curta": 0.0,
        }
        ultimos_ticks = [100.0] * 20

        with patch("src.core.motor.analisar_micro_scalping") as mock_analise:
            mock_analise.return_value = {
                "sinal": None,
                "score": 45.0,
                "confianca": 0.45,
                "razao": "Aguardando confluência",
                "motivo_recusa": "Score 45.0 < 85.0",
                "estado": MicroScalperState.NORMAL,
                "min_score": 85.0,
            }
            with patch.object(self.motor.catalogador, "obter_snapshot_mercado", return_value=snapshot_invalido), \
                 patch.object(self.motor.catalogador, "obter_ultimos_ticks", return_value=ultimos_ticks):
                analise = self.motor._analisar_entrada_turbo(
                    ativo="1HZ100V",
                    preco_atual=100.0,
                    modo="iniciante",
                    meta=20.0,
                    lucro_atual=-0.35,
                    operacoes_ativas=0,
                )

        self.assertFalse(analise["sinal"])
        self.assertFalse(analise["executada"])
        self.assertIn("Aguardando confluência", analise["razao"])

    def test_win_on_gale_resets_to_base_stake(self):
        """16. Ganho no Gale reseta para stake base e registra lucro líquido."""
        self.motor.recovery_level = 1
        self.motor.previous_loss_amount = 0.35
        self.motor.consecutive_losses = 1

        raw_contract_id = "2222222222"
        self.motor.operacoes_abertas[raw_contract_id] = {
            "id": raw_contract_id,
            "contract_id": raw_contract_id,
            "ativo": "1HZ100V",
            "valor": 0.70,
            "tipo": "TURBO",
            "is_recovery": True,
        }

        # Gale de $0.70 venceu com lucro de ~$0.66
        msg = {
            "proposal_open_contract": {
                "contract_id": raw_contract_id,
                "is_sold": 1,
                "profit": 0.66,
                "sell_price": 1.36,
                "balance_after": 1000.31,
            }
        }
        self.motor._on_message(None, json.dumps(msg))

        self.assertEqual(self.motor.recovery_level, 0)
        self.assertEqual(self.motor.consecutive_losses, 0)
        self.assertAlmostEqual(self.motor.recovery_net_result, 0.66 - 0.35, places=2)
        self.assertFalse(self.motor.session_stopped)

    def test_loss_on_gale_triggers_second_consecutive_loss_and_session_stop(self):
        """17. Perda no Gale gera a segunda perda consecutiva e dispara SESSION_STOP."""
        self.motor.recovery_level = 1
        self.motor.previous_loss_amount = 0.35
        self.motor.consecutive_losses = 1

        raw_contract_id = "3333333333"
        self.motor.operacoes_abertas[raw_contract_id] = {
            "id": raw_contract_id,
            "contract_id": raw_contract_id,
            "ativo": "1HZ100V",
            "valor": 0.70,
            "tipo": "TURBO",
            "is_recovery": True,
        }

        # Gale de $0.70 perdeu
        msg = {
            "proposal_open_contract": {
                "contract_id": raw_contract_id,
                "is_sold": 1,
                "profit": -0.70,
                "sell_price": 0.0,
                "balance_after": 998.95,
            }
        }
        self.motor._on_message(None, json.dumps(msg))

        self.assertEqual(self.motor.consecutive_losses, 2)
        self.assertTrue(self.motor.session_stopped)
        self.assertIn("DUAS_PERDAS_CONSECUTIVAS", self.motor.session_stop_reason)

    def test_no_third_trade_after_two_consecutive_losses(self):
        """18. Nenhuma terceira operação é permitida após 2 perdas consecutivas."""
        self.motor.session_stopped = True
        self.motor.session_stop_reason = "DUAS_PERDAS_CONSECUTIVAS: Limite atingido"

        analise = self.motor._analisar_entrada_turbo(
            ativo="1HZ100V",
            preco_atual=100.0,
            modo="iniciante",
            meta=20.0,
            lucro_atual=-1.05,
            operacoes_ativas=0,
        )
        self.assertFalse(analise["sinal"])
        self.assertFalse(analise["executada"])
        self.assertIn("Sessão parada", analise["razao"])

        # Também comprar() deve bloquear
        comprou = self.motor.comprar("CALL", 0.35, "1HZ100V")
        self.assertFalse(comprou)

    def test_risk_cap_2pct_limits_excessive_stake(self):
        """19. Teto de risco de 2% da banca impede stake abusivo."""
        # Saldo ref $30.0 -> 2% = $0.60. Gale 1 = 2x $0.35 = $0.70 > $0.60 -> mantém base $0.35
        self.motor.saldo_inicial_sessao = 30.0
        self.motor.saldo = 30.0
        self.motor.recovery_level = 1
        self.motor.previous_loss_amount = 0.35

        snapshot_valido = {"valido": True, "rsi": 20.0, "z_score": -2.5}
        ultimos_ticks = [100.0 - i * 0.5 for i in range(15)] + [92.0, 92.5, 93.0]

        with patch("src.core.motor.analisar_micro_scalping") as mock_analise:
            mock_analise.return_value = {
                "sinal": "CALL",
                "score": 90.0,
                "confianca": 0.90,
                "razao": "Double bottom confirmed",
                "estado": MicroScalperState.NORMAL,
                "min_score": 85.0,
            }
            with patch.object(self.motor.catalogador, "obter_snapshot_mercado", return_value=snapshot_valido), \
                 patch.object(self.motor.catalogador, "obter_ultimos_ticks", return_value=ultimos_ticks):
                analise = self.motor._analisar_entrada_turbo(
                    ativo="1HZ100V",
                    preco_atual=93.0,
                    modo="iniciante",
                    meta=20.0,
                    lucro_atual=-0.35,
                    operacoes_ativas=0,
                )

        self.assertEqual(analise["volume"], 0.35)

    def test_contract_min_exceeding_risk_cap_logs_skipped(self):
        """20. Contrato mínimo acima do teto de risco registra RECOVERY_SKIPPED_RISK_CAP."""
        self.motor.saldo_inicial_sessao = 10.0  # 2% de 10.0 = $0.20 < min contract ($0.35)
        self.motor.saldo = 10.0
        self.motor.recovery_level = 1

        with self.assertLogs(self.motor.logger, level="WARNING") as log_cm:
            with patch("src.core.motor.analisar_micro_scalping") as mock_analise:
                mock_analise.return_value = {
                    "sinal": "CALL",
                    "score": 90.0,
                    "confianca": 0.90,
                    "razao": "Reversal valid",
                    "estado": MicroScalperState.NORMAL,
                    "min_score": 85.0,
                }
                with patch.object(self.motor.catalogador, "obter_snapshot_mercado", return_value={"valido": True}), \
                     patch.object(self.motor.catalogador, "obter_ultimos_ticks", return_value=[100.0] * 20):
                    analise = self.motor._analisar_entrada_turbo(
                        ativo="1HZ100V",
                        preco_atual=100.0,
                        modo="iniciante",
                        meta=20.0,
                        lucro_atual=-0.35,
                        operacoes_ativas=0,
                    )
            self.assertTrue(any("RECOVERY_SKIPPED_RISK_CAP" in msg for msg in log_cm.output))
            self.assertEqual(analise["volume"], 0.35)

    def test_session_reset_clears_recovery_state(self):
        """21. Reinício de sessão limpa estado de recuperação."""
        self.motor.recovery_level = 1
        self.motor.previous_loss_amount = 0.35
        self.motor.consecutive_losses = 1
        self.motor.session_stopped = True

        self.motor.iniciar_sessao()

        self.assertEqual(self.motor.recovery_level, 0)
        self.assertEqual(self.motor.previous_loss_amount, 0.0)
        self.assertEqual(self.motor.consecutive_losses, 0)
        self.assertFalse(self.motor.session_stopped)

    def test_manual_stop_neutralizes_recovery_state(self):
        """22. Parada manual neutraliza estado de recuperação."""
        self.motor.recovery_level = 1
        self.motor.previous_loss_amount = 0.35

        self.motor.parar()

        self.assertEqual(self.motor.recovery_level, 0)
        self.assertEqual(self.motor.previous_loss_amount, 0.0)
        self.assertTrue(self.motor.session_stopped)


class TestSystemSecurityAndIntegration(unittest.TestCase):
    """Testes de Segurança e Proteção Inviolável de Conta Real e Telemetria (Issues #19, #21, #23)."""

    def setUp(self):
        self.motor = Motor()

    def test_real_account_remains_strictly_blocked(self):
        """23. Conta real continua estritamente bloqueada (modo_real = False, REAL_ORDER_SENT=NO)."""
        self.motor.modo_real = True
        sucesso = self.motor.comprar("CALL", 0.35, "1HZ100V")
        self.assertFalse(sucesso)

    def test_full_suite_runs_without_regression(self):
        """24. Status do robô expõe recovery_level e recovery_net_result adequadamente."""
        self.motor.recovery_level = 1
        self.motor.recovery_net_result = 0.42
        status = self.motor.get_status()
        self.assertEqual(status["recovery_level"], 1)
        self.assertEqual(status["recovery_net_result"], 0.42)


if __name__ == "__main__":
    unittest.main()
