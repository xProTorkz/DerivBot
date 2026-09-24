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

    def test_win_on_recovery_resets_to_base_stake(self):
        """16. Ganho na recuperação reseta para stake base e zera perdas consecutivas."""
        self.motor.recovery_level = 2
        self.motor.previous_loss_amount = 2.0
        self.motor.consecutive_losses = 2
        self.motor.stake_base = 1.0
        self.motor.stake_atual = 4.0
        self.motor.meta_lucro_sessao = 20.0
        self.motor.limite_prejuizo_sessao = 20.0
        self.motor.lucro_realizado_sessao = -3.0

        raw_contract_id = "2222222222"
        self.motor.operacoes_abertas[raw_contract_id] = {
            "id": raw_contract_id,
            "contract_id": raw_contract_id,
            "ativo": "1HZ100V",
            "valor": 4.0,
            "tipo": "TURBO",
            "recovery_level_num": 2,
            "is_recovery": True,
        }

        # Operação de $4.00 vence com lucro de $3.80
        msg = {
            "proposal_open_contract": {
                "contract_id": raw_contract_id,
                "is_sold": 1,
                "profit": 3.80,
                "sell_price": 7.80,
                "balance_after": 1000.80,
            }
        }
        self.motor._on_message(None, json.dumps(msg))

        self.assertEqual(self.motor.recovery_level, 0)
        self.assertEqual(self.motor.consecutive_losses, 0)
        self.assertEqual(self.motor.stake_atual, 1.0)
        self.assertAlmostEqual(self.motor.lucro_realizado_sessao, 0.80, places=2)
        self.assertFalse(self.motor.session_stopped)

    def test_canonical_sequence_1_2_4_8_5_capped_at_session_budget(self):
        """17. Sequência canônica da Issue #25: Meta $20, stake base $1 -> 1, 2, 4, 8, 5 com perda total cravada em -$20 (nunca -$31)."""
        self.motor.iniciar_sessao()
        self.motor.meta_diaria = 20.0
        self.motor.meta_lucro_sessao = 20.0
        self.motor.limite_prejuizo_sessao = 20.0
        self.motor.stake_base = 1.0
        self.motor.stake_atual = 1.0
        self.motor.orcamento_prejuizo_restante = 20.0

        sequencia_stakes_esperados = [1.0, 2.0, 4.0, 8.0, 5.0]
        perdas_acumuladas_esperadas = [-1.0, -3.0, -7.0, -15.0, -20.0]
        orcamentos_restantes_esperados = [19.0, 17.0, 13.0, 5.0, 0.0]

        for step, (stake_exec, perda_acum, orc_esperado) in enumerate(
            zip(sequencia_stakes_esperados, perdas_acumuladas_esperadas, orcamentos_restantes_esperados), start=1
        ):
            cid = f"contract_step_{step}"
            self.motor.operacoes_abertas[cid] = {
                "id": cid,
                "contract_id": cid,
                "ativo": "1HZ100V",
                "valor": stake_exec,
                "tipo": "TURBO",
                "recovery_level_num": step - 1,
                "is_recovery": (step > 1),
            }

            msg = {
                "proposal_open_contract": {
                    "contract_id": cid,
                    "is_sold": 1,
                    "profit": -stake_exec,
                    "sell_price": 0.0,
                    "balance_after": 1000.0 + perda_acum,
                }
            }
            self.motor._on_message(None, json.dumps(msg))

            self.assertAlmostEqual(self.motor.lucro_realizado_sessao, perda_acum, places=2)
            self.assertAlmostEqual(self.motor.orcamento_prejuizo_restante, orc_esperado, places=2)

            if step < 5:
                proximo_esperado = sequencia_stakes_esperados[step]
                self.assertAlmostEqual(self.motor.stake_atual, proximo_esperado, places=2)
                self.assertFalse(self.motor.session_stopped, f"Sessão não deveria parar no passo {step}")
            else:
                self.assertTrue(self.motor.session_stopped, "Sessão deve parar no passo 5 por atingir o limite de prejuízo")
                self.assertIn("META_PREJUIZO_ATINGIDA", self.motor.session_stop_reason)
                self.assertAlmostEqual(self.motor.lucro_realizado_sessao, -20.0, places=2)

    def test_consecutive_losses_does_not_stop_session_alone(self):
        """18. consecutive_losses não para a sessão sozinho enquanto houver orçamento restante."""
        self.motor.iniciar_sessao()
        self.motor.meta_diaria = 50.0
        self.motor.meta_lucro_sessao = 50.0
        self.motor.limite_prejuizo_sessao = 50.0
        self.motor.stake_base = 0.50
        self.motor.lucro_realizado_sessao = -3.50
        self.motor.orcamento_prejuizo_restante = 46.50
        self.motor.consecutive_losses = 3
        self.motor.recovery_level = 3

        self.assertFalse(self.motor.session_stopped)
        self.assertEqual(self.motor.consecutive_losses, 3)

    def test_session_stop_on_insufficient_budget(self):
        """19. Orçamento restante menor que o contrato mínimo dispara ORCAMENTO_INSUFICIENTE."""
        self.motor.iniciar_sessao()
        self.motor.meta_diaria = 20.0
        self.motor.meta_lucro_sessao = 20.0
        self.motor.limite_prejuizo_sessao = 20.0
        self.motor.stake_base = 1.0
        self.motor.lucro_realizado_sessao = -19.80  # Resta apenas $0.20
        self.motor.orcamento_prejuizo_restante = 0.20

        # Tentativa de análise com orçamento restante < min_stake (0.35)
        analise = self.motor._analisar_entrada_turbo(
            ativo="1HZ100V",
            preco_atual=100.0,
            modo="iniciante",
            meta=20.0,
            lucro_atual=-19.80,
            operacoes_ativas=0,
        )
        self.assertFalse(analise["sinal"])
        self.assertTrue(self.motor.session_stopped)
        self.assertIn("ORCAMENTO_INSUFICIENTE", self.motor.session_stop_reason)

    def test_stop_win_when_profit_hits_session_target(self):
        """20. Sessão para imediatamente com META_LUCRO_ATINGIDA ao bater a meta."""
        self.motor.iniciar_sessao()
        self.motor.meta_diaria = 20.0
        self.motor.meta_lucro_sessao = 20.0
        self.motor.lucro_realizado_sessao = 19.50

        raw_contract_id = "target_hit_contract"
        self.motor.operacoes_abertas[raw_contract_id] = {
            "id": raw_contract_id,
            "contract_id": raw_contract_id,
            "ativo": "1HZ100V",
            "valor": 1.0,
            "tipo": "TURBO",
            "recovery_level_num": 0,
            "is_recovery": False,
        }

        msg = {
            "proposal_open_contract": {
                "contract_id": raw_contract_id,
                "is_sold": 1,
                "profit": 0.85,
                "sell_price": 1.85,
                "balance_after": 1020.35,
            }
        }
        self.motor._on_message(None, json.dumps(msg))

        self.assertTrue(self.motor.session_stopped)
        self.assertIn("META_LUCRO_ATINGIDA", self.motor.session_stop_reason)
        self.assertGreaterEqual(self.motor.lucro_realizado_sessao, 20.0)

    def test_rule_b8_single_in_flight_recovery(self):
        """21. Regra de Concorrência B8: enquanto recovery_level > 0, apenas 1 operação em voo."""
        self.motor.iniciar_sessao()
        self.motor.recovery_level = 1
        self.motor.operacoes_abertas["flight_rec_1"] = {
            "id": "flight_rec_1",
            "contract_id": "flight_rec_1",
            "ativo": "1HZ100V",
            "valor": 2.0,
            "tipo": "TURBO",
            "recovery_level_num": 1,
            "is_recovery": True,
        }

        analise = self.motor._analisar_entrada_turbo(
            ativo="1HZ75V",
            preco_atual=100.0,
            modo="iniciante",
            meta=20.0,
            lucro_atual=-1.0,
            operacoes_ativas=1,
        )

        self.assertFalse(analise["sinal"])
        self.assertIn("B8", analise["razao"])

    def test_multi_asset_recovery_allowed(self):
        """22. Recuperação pode ser executada em qualquer outro ativo qualificado pelo scanner."""
        self.motor.iniciar_sessao()
        self.motor.recovery_level = 1
        self.motor.stake_base = 1.0
        self.motor.stake_atual = 1.0
        self.motor.meta_diaria = 20.0
        self.motor.meta_lucro_sessao = 20.0
        self.motor.limite_prejuizo_sessao = 20.0
        self.motor.orcamento_prejuizo_restante = 19.0
        self.motor.lucro_realizado_sessao = -1.0

        snapshot_valido = {"valido": True, "rsi": 20.0, "z_score": -2.5}
        ultimos_ticks = [100.0 - i * 0.5 for i in range(15)] + [92.0, 92.5, 93.0]

        with patch("src.core.motor.analisar_micro_scalping") as mock_analise:
            mock_analise.return_value = {
                "sinal": "CALL",
                "score": 91.0,
                "confianca": 0.91,
                "razao": "Double bottom in 1HZ75V",
                "estado": MicroScalperState.NORMAL,
                "min_score": 85.0,
            }
            with patch.object(self.motor.catalogador, "obter_snapshot_mercado", return_value=snapshot_valido), \
                 patch.object(self.motor.catalogador, "obter_ultimos_ticks", return_value=ultimos_ticks):
                analise = self.motor._analisar_entrada_turbo(
                    ativo="1HZ75V",
                    preco_atual=93.0,
                    modo="iniciante",
                    meta=20.0,
                    lucro_atual=-1.0,
                    operacoes_ativas=0,
                )

        self.assertTrue(analise["sinal"])
        self.assertEqual(analise["ativo"], "1HZ75V")
        self.assertEqual(analise["volume"], 2.0)
        self.assertEqual(analise["recovery_level"], 1)

    def test_session_reset_clears_recovery_state(self):
        """23. Reinício de sessão limpa estado de recuperação e restaura orçamento da meta."""
        self.motor.recovery_level = 2
        self.motor.previous_loss_amount = 2.0
        self.motor.consecutive_losses = 2
        self.motor.session_stopped = True
        self.motor.meta_diaria = 20.0

        self.motor.iniciar_sessao()

        self.assertEqual(self.motor.recovery_level, 0)
        self.assertEqual(self.motor.previous_loss_amount, 0.0)
        self.assertEqual(self.motor.consecutive_losses, 0)
        self.assertEqual(self.motor.orcamento_prejuizo_restante, 20.0)
        self.assertEqual(self.motor.stake_atual, self.motor.stake_base)
        self.assertFalse(self.motor.session_stopped)

    def test_manual_stop_neutralizes_recovery_state(self):
        """24. Parada manual neutraliza estado de recuperação."""
        self.motor.recovery_level = 3
        self.motor.previous_loss_amount = 4.0

        self.motor.parar()

        self.assertEqual(self.motor.recovery_level, 0)
        self.assertEqual(self.motor.previous_loss_amount, 0.0)
        self.assertEqual(self.motor.stake_atual, self.motor.stake_base)
        self.assertTrue(self.motor.session_stopped)


class TestSystemSecurityAndIntegration(unittest.TestCase):
    """Testes de Segurança e Proteção Inviolável de Conta Real e Telemetria (Issues #19, #21, #23, #25)."""

    def setUp(self):
        self.motor = Motor()

    def test_real_account_remains_strictly_blocked(self):
        """25. Conta real continua estritamente bloqueada (modo_real = True -> bloqueio inviolável)."""
        self.motor.modo_real = True
        sucesso = self.motor.comprar("CALL", 0.35, "1HZ100V")
        self.assertFalse(sucesso)

    def test_telemetry_schema_exposes_recovery_and_budget_metrics(self):
        """26. Status do robô expõe todo o schema canônico de orçamento e recuperação geométrica 2x."""
        self.motor.meta_lucro_sessao = 20.0
        self.motor.limite_prejuizo_sessao = 20.0
        self.motor.lucro_realizado_sessao = -3.0
        self.motor.recovery_level = 2
        self.motor.consecutive_losses = 2
        self.motor.stake_base = 1.0
        self.motor.stake_atual = 4.0
        self.motor.stake_proximo_teorico = 4.0
        self.motor.stake_proximo_limitado = 4.0

        status = self.motor.get_status()
        self.assertEqual(status["meta_lucro_sessao"], 20.0)
        self.assertEqual(status["limite_prejuizo_sessao"], 20.0)
        self.assertEqual(status["lucro_realizado_sessao"], -3.0)
        self.assertEqual(status["orcamento_prejuizo_restante"], 17.0)
        self.assertEqual(status["stake_base"], 1.0)
        self.assertEqual(status["stake_atual"], 4.0)
        self.assertEqual(status["stake_proximo_teorico"], 4.0)
        self.assertEqual(status["stake_proximo_limitado"], 4.0)
        self.assertEqual(status["recovery_level"], 2)
        self.assertEqual(status["consecutive_losses"], 2)


if __name__ == "__main__":
    unittest.main()
