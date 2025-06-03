#!/usr/bin/env python3
"""
Script de teste para verificar se todos os imports estão funcionando
"""

print("Testando imports...")

try:
    print("1. Testando import do motor...")
    from src.core.motor import Motor
    print("✅ Motor importado com sucesso!")
except Exception as e:
    print(f"❌ Erro ao importar Motor: {e}")

try:
    print("2. Testando import do catalogador...")
    from src.core.catalogador import Catalogador
    print("✅ Catalogador importado com sucesso!")
except Exception as e:
    print(f"❌ Erro ao importar Catalogador: {e}")

try:
    print("3. Testando import do config...")
    from src import config
    print("✅ Config importado com sucesso!")
except Exception as e:
    print(f"❌ Erro ao importar Config: {e}")

print("Teste de imports concluído!")
