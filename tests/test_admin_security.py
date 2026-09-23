#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Testes de segurança e conformidade da Issue #1:
- Eliminação de fallbacks hardcoded de licenças administrativas
- Carregamento de ADMIN_LICENSES exclusivamente de ambiente ou arquivo local ignorado
- Fail-closed na ausência de configuração
- Redação/ofuscação de credenciais em logs
- Ausência de segredos na árvore rastreada do Git
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
import subprocess

# Garante inclusão de src no path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE_DIR, "src")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from src.config.config import Config
from src.main import ofuscar_segredo, verificar_acesso_admin, app


class TestAdminSecurity(unittest.TestCase):
    """Validações de segurança administrativa e higienização"""

    def setUp(self):
        self.orig_env = os.environ.get("ADMIN_LICENSES")
        self.orig_data_dir = Config.DATA_DIR
        self.temp_dir = tempfile.mkdtemp()
        Config.DATA_DIR = self.temp_dir

    def tearDown(self):
        if self.orig_env is not None:
            os.environ["ADMIN_LICENSES"] = self.orig_env
        elif "ADMIN_LICENSES" in os.environ:
            del os.environ["ADMIN_LICENSES"]
        Config.DATA_DIR = self.orig_data_dir
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_admin_licenses_from_env(self):
        """ADMIN_LICENSES deve carregar corretamente a partir de variável de ambiente"""
        os.environ["ADMIN_LICENSES"] = "ADMIN-ENV-01, ADMIN-ENV-02 , ADMIN-ENV-03"
        licenses = Config.obter_admin_licenses()
        self.assertEqual(licenses, ["ADMIN-ENV-01", "ADMIN-ENV-02", "ADMIN-ENV-03"])
        self.assertEqual(Config.ADMIN_LICENSES, ["ADMIN-ENV-01", "ADMIN-ENV-02", "ADMIN-ENV-03"])

    def test_admin_licenses_from_local_file(self):
        """ADMIN_LICENSES deve carregar a partir de data/admin_config.json ignorado quando env não existir"""
        if "ADMIN_LICENSES" in os.environ:
            del os.environ["ADMIN_LICENSES"]

        config_path = os.path.join(self.temp_dir, "admin_config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"admin_licenses": ["LOCAL-ADMIN-A", "LOCAL-ADMIN-B"]}, f)

        licenses = Config.obter_admin_licenses()
        self.assertEqual(licenses, ["LOCAL-ADMIN-A", "LOCAL-ADMIN-B"])
        self.assertEqual(Config.ADMIN_LICENSES, ["LOCAL-ADMIN-A", "LOCAL-ADMIN-B"])

    def test_admin_licenses_fail_closed_when_no_config(self):
        """Quando não há variável de ambiente nem arquivo local, deve retornar lista vazia (fail-closed)"""
        if "ADMIN_LICENSES" in os.environ:
            del os.environ["ADMIN_LICENSES"]

        licenses = Config.obter_admin_licenses()
        self.assertEqual(licenses, [])
        self.assertEqual(Config.ADMIN_LICENSES, [])

    def test_no_hardcoded_admin_secret_fallback(self):
        """Garante que a antiga licença hardcoded nunca é retornada por padrão"""
        if "ADMIN_LICENSES" in os.environ:
            del os.environ["ADMIN_LICENSES"]

        old_secret = "DERIVBOT-82YM-E0VX"
        self.assertNotIn(old_secret, Config.obter_admin_licenses())
        self.assertNotIn(old_secret, Config.ADMIN_LICENSES)

    def test_verificar_acesso_admin_fail_closed(self):
        """verificar_acesso_admin deve rejeitar com fail-closed se não houver licença admin configurada"""
        if "ADMIN_LICENSES" in os.environ:
            del os.environ["ADMIN_LICENSES"]

        with app.test_request_context("/api/admin/stats"):
            from flask import session
            session["token"] = "valid_test_token"
            session["codigo_licenca"] = "ANY-LICENSE"

            autorizado, mensagem = verificar_acesso_admin()
            self.assertFalse(autorizado)
            self.assertEqual(mensagem, "Acesso administrativo não configurado")

    def test_verificar_acesso_admin_authorized(self):
        """verificar_acesso_admin deve autorizar quando a licença bate com ADMIN_LICENSES configurada"""
        os.environ["ADMIN_LICENSES"] = "ADMIN-VALID-123"

        with app.test_request_context("/api/admin/stats"):
            from flask import session
            session["token"] = "valid_test_token"
            session["codigo_licenca"] = "ADMIN-VALID-123"

            autorizado, mensagem = verificar_acesso_admin()
            self.assertTrue(autorizado)
            self.assertEqual(mensagem, "Autorizado")

    def test_verificar_acesso_admin_denied_for_unauthorized_user(self):
        """verificar_acesso_admin deve negar acesso a usuário com licença comum não admin"""
        os.environ["ADMIN_LICENSES"] = "ADMIN-VALID-123"

        with app.test_request_context("/api/admin/stats"):
            from flask import session
            session["token"] = "valid_test_token"
            session["codigo_licenca"] = "USER-COMMON-456"

            autorizado, mensagem = verificar_acesso_admin()
            self.assertFalse(autorizado)
            self.assertEqual(mensagem, "Acesso negado")

    def test_ofuscar_segredo_masks_credentials(self):
        """Função de ofuscação deve mascarar tokens, senhas e licenças preservando apenas extremidades seguras"""
        # Licença completa
        licenca = "DERIVBOT-ABCD-1234"
        ofuscada = ofuscar_segredo(licenca)
        self.assertTrue(ofuscada.startswith("DERI"))
        self.assertTrue(ofuscada.endswith("34"))
        self.assertIn("***", ofuscada)
        self.assertNotIn("ABCD", ofuscada)

        # Token PAT
        pat = "pat_7a5512a8d6788925fa83fac78ca0"
        ofuscada_pat = ofuscar_segredo(pat)
        self.assertTrue(ofuscada_pat.startswith("pat_"))
        self.assertTrue(ofuscada_pat.endswith("a0"))
        self.assertIn("***", ofuscada_pat)
        self.assertNotIn("d6788925fa83fac", ofuscada_pat)

        # Chave muito curta (deve mascarar 100%)
        self.assertEqual(ofuscar_segredo("curto"), "***")
        self.assertEqual(ofuscar_segredo(""), "")
        self.assertEqual(ofuscar_segredo(None), "")

    def test_no_hardcoded_admin_licenses_in_tracked_git_tree(self):
        """Varre os arquivos rastreados pelo Git para garantir que nenhuma chave administrativa padrão existe"""
        res = subprocess.run(
            ["git", "grep", "-i", "-E", "82YM-E0VX"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            res.returncode,
            1,
            f"Encontradas ocorrências de 82YM-E0VX em arquivos rastreados:\n{res.stdout}",
        )


if __name__ == "__main__":
    unittest.main()
