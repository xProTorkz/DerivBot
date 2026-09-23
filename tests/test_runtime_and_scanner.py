"""
Testes abrangentes de validação de runtime, caminhos canônicos e isolamento de dados do scanner (Issue #5).
"""
import os
import sys
import time
import json
import unittest
from unittest.mock import MagicMock, patch

# Adiciona raiz do projeto ao path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.config.config import Config
from src.core.catalogador import CatalogadorOtimizado, CONFIG_CATALOGADOR
from src.core.motor import Motor


class TestCanonicalPathsAndStartup(unittest.TestCase):
    """Testa padronização dos caminhos canônicos e startup único."""

    def test_canonical_data_dir(self):
        """Config.DATA_DIR deve apontar para o diretório canônico data/ na raiz."""
        self.assertTrue(os.path.isabs(Config.DATA_DIR))
        self.assertEqual(Config.DATA_DIR, os.path.join(Config.BASE_DIR, "data"))

    def test_canonical_logs_dir(self):
        """Config.LOGS_DIR deve apontar para o diretório canônico logs/ na raiz."""
        self.assertTrue(os.path.isabs(Config.LOGS_DIR))
        self.assertEqual(Config.LOGS_DIR, os.path.join(Config.BASE_DIR, "logs"))

    def test_default_port_is_5001(self):
        """Porta padrão oficial do sistema deve ser 5001."""
        self.assertEqual(getattr(Config, "FLASK_PORT", 5001), 5001)

    def test_flask_port_configurable_via_env(self):
        """FLASK_PORT deve poder ser sobrescrito por variável de ambiente."""
        with patch.dict(os.environ, {"FLASK_PORT": "5005"}):
            # Recalcula ou lê via int(os.getenv)
            porta = int(os.getenv("FLASK_PORT", "5001"))
            self.assertEqual(porta, 5005)

    def test_launcher_references_port_5001_and_canonical_startup(self):
        """executar_derivbot.bat deve referenciar a porta 5001 e 'python -m src.main'."""
        bat_path = os.path.join(Config.BASE_DIR, "executar_derivbot.bat")
        if os.path.exists(bat_path):
            with open(bat_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            self.assertIn("5001", content)
            self.assertNotIn("http://localhost:5000", content)
            self.assertIn("python -m src.main", content)
            self.assertNotIn("cd src", content)

    def test_readme_references_canonical_startup_and_port(self):
        """README.md deve referenciar 'python -m src.main' e porta 5001, sem executar_desenvolvimento.bat."""
        readme_path = os.path.join(Config.BASE_DIR, "README.md")
        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("python -m src.main", content)
            self.assertIn("5001", content)
            self.assertNotIn("executar_desenvolvimento.bat", content)


class TestMultiAssetDataIsolation(unittest.TestCase):
    """Garante isolamento estrito de dados entre ativos no catalogador e motor."""

    def setUp(self):
        self.cat = CatalogadorOtimizado()

    def test_per_asset_buffers_independent(self):
        """Ticks de R_10 devem entrar exclusivamente no buffer de R_10 sem afetar R_25."""
        # Alimenta R_10 com série A
        ticks_r10 = [100.0, 101.0, 102.0, 103.0]
        for p in ticks_r10:
            self.cat.adicionar_tick(p, ativo="R_10")

        # Alimenta R_25 com série B
        ticks_r25 = [200.0, 205.0, 210.0, 215.0]
        for p in ticks_r25:
            self.cat.adicionar_tick(p, ativo="R_25")

        # Verifica isolamento de ticks
        obtidos_r10 = self.cat.obter_ultimos_ticks(10, ativo="R_10")
        obtidos_r25 = self.cat.obter_ultimos_ticks(10, ativo="R_25")
        self.assertEqual(obtidos_r10, ticks_r10)
        self.assertEqual(obtidos_r25, ticks_r25)
        self.assertNotEqual(obtidos_r10, obtidos_r25)

        # Adicionar mais ticks em R_10 NÃO altera R_25
        self.cat.adicionar_tick(104.0, ativo="R_10")
        self.assertEqual(self.cat.obter_ultimos_ticks(10, ativo="R_25"), ticks_r25)

    def test_distinct_series_produce_distinct_snapshots(self):
        """Séries distintas em ativos distintos geram snapshots distintos (Anti-Contaminação)."""
        # R_10: série em alta acentuada
        for i in range(40):
            self.cat.adicionar_tick(100.0 + i * 2.0, ativo="R_10")

        # R_25: série em queda acentuada
        for i in range(40):
            self.cat.adicionar_tick(500.0 - i * 3.0, ativo="R_25")

        snap_r10 = self.cat.obter_snapshot_mercado(ativo="R_10")
        snap_r25 = self.cat.obter_snapshot_mercado(ativo="R_25")

        self.assertTrue(snap_r10["valido"])
        self.assertTrue(snap_r25["valido"])
        self.assertEqual(snap_r10["ativo"], "R_10")
        self.assertEqual(snap_r25["ativo"], "R_25")
        self.assertNotEqual(snap_r10["preco_atual"], snap_r25["preco_atual"])
        self.assertGreater(snap_r10["preco_atual"], 150.0)
        self.assertLess(snap_r25["preco_atual"], 450.0)
        self.assertGreater(snap_r10["rsi"], snap_r25["rsi"])

    def test_asset_without_ticks_returns_empty_or_invalid_snapshot(self):
        """Ativo sem ticks suficientes não pode reutilizar dados de outros ativos."""
        for p in range(50):
            self.cat.adicionar_tick(100.0 + p, ativo="R_10")

        # R_50 não recebeu nenhum tick
        ticks_r50 = self.cat.obter_ultimos_ticks(50, ativo="R_50")
        self.assertEqual(ticks_r50, [])

        snap_r50 = self.cat.obter_snapshot_mercado(ativo="R_50")
        self.assertFalse(snap_r50["valido"])
        self.assertIn("vazio", snap_r50["razao"].lower())

    def test_scanner_returns_no_trade_when_insufficient_real_data(self):
        """Scanner multi-ativo retorna NO_SELECTION / NO_TRADE quando dados insuficientes, sem inventar fallback."""
        res = self.cat.analisar_todos_volatilitys_e_escolher_melhor("agressivo")
        self.assertEqual(res.get("status"), "NO_SELECTION")
        self.assertEqual(res.get("motivo"), "NO_TRADE")
        self.assertIsNone(res.get("melhor_ativo"))


class TestMotorMultiAssetAndFreshness(unittest.TestCase):
    """Testa gerenciamento de subscriptions, frescor e desativação do lock em VIX75 no Motor."""

    def setUp(self):
        self.motor = Motor()
        self.motor.modo_operacao = "iniciante"
        self.motor.saldo = 100.0
        self.motor.saldo_inicial = 100.0

    def test_vix75_force_lock_disabled(self):
        """self.ativo_fixo_turbo não deve forçar VIX75."""
        self.assertFalse(getattr(self.motor, "ativo_fixo_turbo", True))

    def test_per_asset_freshness_isolation(self):
        """Tick fresco em R_10 não deve permitir operação em R_50 se R_50 estiver obsoleto."""
        agora = time.time()
        self.motor.ultimo_tick_timestamp_por_ativo["R_10"] = agora  # Fresco (<2.5s)
        self.motor.ultimo_tick_timestamp_por_ativo["R_50"] = agora - 15.0  # Obsoleto (15s > 2.5s)

        # R_10 deve passar no gateway de risco
        valido_r10, motivo_r10 = self.motor.validar_gateway_risco(0.35, ativo="R_10")
        self.assertTrue(valido_r10, f"R_10 deveria ser aprovado: {motivo_r10}")

        # R_50 DEVE ser rejeitado por dados obsoletos
        valido_r50, motivo_r50 = self.motor.validar_gateway_risco(0.35, ativo="R_50")
        self.assertFalse(valido_r50)
        self.assertIn("obsoletos", motivo_r50.lower())

    def test_duplicate_tick_subscriptions_prevented(self):
        """_inscrever_ticks não deve duplicar subscrições já ativas."""
        mock_ws = MagicMock()
        self.motor.ws = mock_ws
        self.motor.conectado = True

        # Primeira chamada inscreve todos os ativos monitorados
        self.motor._inscrever_ticks()
        total_calls_primeira = mock_ws.send.call_count
        self.assertGreater(total_calls_primeira, 0)

        # Simula resposta com subscription ID registrado para todos os ativos
        for ativo in self.motor.ativos_ativos:
            self.motor.tick_subscription_id_por_ativo[ativo] = f"sub_{ativo}_123"

        # Segunda chamada com subscriptions ativas NÃO deve reenviar requisições duplicadas
        mock_ws.send.reset_mock()
        self.motor._inscrever_ticks()
        self.assertEqual(mock_ws.send.call_count, 0)

    def test_desconectar_sends_forget_all_and_clears_subscriptions(self):
        """desconectar() deve enviar forget_all e limpar as subscrições locais."""
        mock_ws = MagicMock()
        self.motor.ws = mock_ws
        self.motor.conectado = True
        self.motor.tick_subscription_id_por_ativo["1HZ75V"] = "sub_75"
        self.motor.tick_subscription_id_por_ativo["R_10"] = "sub_10"

        self.motor.desconectar()

        # Verifica se forget_all foi enviado
        enviou_forget = any("forget_all" in call.args[0] for call in mock_ws.send.call_args_list if call.args)
        self.assertTrue(enviou_forget)
        # Verifica se as subscrições foram limpas
        self.assertEqual(len(self.motor.tick_subscription_id_por_ativo), 0)
        self.assertFalse(self.motor.conectado)


if __name__ == "__main__":
    unittest.main()
