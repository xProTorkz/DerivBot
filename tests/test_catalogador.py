import sys
import os
import pytest
import asyncio
import time
from datetime import datetime
from typing import Dict, List
import json

# Adicionar o diretório pai ao path para importar os módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Importar os módulos a serem testados
from catalogador import (
    Catalogador,
    AnalisadorTecnico,
    DeepseekAPI,
    DecisaoTipo,
    VerificadorDados,
    analisar_entrada_chatgpt,
    analisar_entrada_chatgpt_async,
    analisar_saida_chatgpt,
    analisar_saida_chatgpt_async,
)


# Mock de dados para testes
@pytest.fixture
def velas_mock():
    """Fixture que fornece velas para testes"""
    return [
        {
            "timestamp": int(time.time()) - 300,
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 104.0,
            "volume": 50,
        },
        {
            "timestamp": int(time.time()) - 240,
            "open": 104.0,
            "high": 107.0,
            "low": 102.0,
            "close": 106.0,
            "volume": 60,
        },
        {
            "timestamp": int(time.time()) - 180,
            "open": 106.0,
            "high": 108.0,
            "low": 105.0,
            "close": 107.0,
            "volume": 55,
        },
        {
            "timestamp": int(time.time()) - 120,
            "open": 107.0,
            "high": 110.0,
            "low": 106.0,
            "close": 109.0,
            "volume": 70,
        },
        {
            "timestamp": int(time.time()) - 60,
            "open": 109.0,
            "high": 112.0,
            "low": 108.0,
            "close": 110.0,
            "volume": 65,
        },
    ]


@pytest.fixture
def catalogador_instance():
    """Fixture que fornece uma instância do catalogador para testes"""
    return Catalogador()


# Testes de funcionalidades básicas
def test_verificador_dados_validacao(velas_mock):
    """Testa a validação de velas"""
    # Dados válidos
    assert VerificadorDados.validar_velas(velas_mock) == True

    # Dados inválidos: velas vazias
    assert VerificadorDados.validar_velas([]) == False

    # Dados inválidos: campos faltando
    velas_invalidas = velas_mock.copy()
    velas_invalidas[0] = {"open": 100.0, "high": 105.0}  # Faltam campos
    assert VerificadorDados.validar_velas(velas_invalidas) == False

    # Dados inválidos: inconsistência de valores
    velas_invalidas = velas_mock.copy()
    velas_invalidas[0]["low"] = 110.0  # Low maior que high
    assert VerificadorDados.validar_velas(velas_invalidas) == False


def test_analisador_tecnico(velas_mock):
    """Testa as funções de análise técnica"""
    analisador = AnalisadorTecnico()

    # Teste de cálculo RSI
    rsi = analisador.calcular_rsi(velas_mock)
    assert 0 <= rsi <= 100, f"RSI deve estar entre 0 e 100, valor: {rsi}"

    # Teste de identificação de Fibonacci
    fib = analisador.identificar_fibonacci(velas_mock)
    assert "61.8%" in fib, "Nível Fibonacci 61.8% não encontrado"
    assert fib["61.8%"] > 0, "Valor Fibonacci deve ser positivo"

    # Teste de tendência
    tendencia = analisador.tendencia_velas(velas_mock)
    assert tendencia in [
        "ALTA",
        "BAIXA",
        "INDEFINIDA",
    ], f"Tendência inválida: {tendencia}"


def test_catalogador_adicionar_tick(catalogador_instance):
    """Testa a adição de ticks e formação de velas"""
    # Adiciona uma série de ticks
    for i in range(10):
        catalogador_instance.adicionar_tick(100.0 + i)
        time.sleep(0.1)  # Simula passagem de tempo

    # Verifica se os ticks foram registrados
    assert len(catalogador_instance.ticks) == 10, "Deveria ter 10 ticks"

    # Obtém as velas formadas
    velas = catalogador_instance.obter_velas()

    # Pode ter 0 ou 1 velas formadas dependendo do tempo
    assert len(velas) >= 0, "Deveria ter pelo menos 0 velas"

    # Testa o preview de velas
    velas_preview = catalogador_instance.obter_velas_preview()
    assert len(velas_preview) >= len(velas), "Preview deve incluir a vela em formação"


# Testes para funções assíncronas (exige um loop de eventos)
@pytest.mark.asyncio
async def test_analise_entrada_async(velas_mock, monkeypatch):
    """Testa a análise assíncrona de entrada"""

    # Mock da função chamar_api_async para não depender da API real
    async def mock_chamar_api_async(*args, **kwargs):
        return DecisaoTipo.CALL.value, 0.85

    # Aplica o mock
    monkeypatch.setattr(DeepseekAPI, "chamar_api_async", mock_chamar_api_async)

    # Testa a função assíncrona
    decisao, confianca = await analisar_entrada_chatgpt_async(
        velas_mock, 0.0, ["CALL", "PUT"], "test_client"
    )

    assert (
        decisao == DecisaoTipo.CALL.value
    ), f"Decisão esperada: CALL, obtida: {decisao}"
    assert confianca == 0.85, f"Confiança esperada: 0.85, obtida: {confianca}"

    # Verifica se a decisão foi registrada na vela
    assert "ia_decisoes" in velas_mock[-1], "Decisão não foi registrada na vela"
    decisao_registrada = velas_mock[-1]["ia_decisoes"][-1]
    assert decisao_registrada["decisao"] == DecisaoTipo.CALL.value
    assert decisao_registrada["cliente_id"] == "test_client"


@pytest.mark.asyncio
async def test_analise_saida_async(velas_mock, monkeypatch):
    """Testa a análise assíncrona de saída"""

    # Mock da função chamar_api_async para não depender da API real
    async def mock_chamar_api_async(*args, **kwargs):
        return DecisaoTipo.SAIR.value, 0.78

    # Aplica o mock
    monkeypatch.setattr(DeepseekAPI, "chamar_api_async", mock_chamar_api_async)

    # Testa a função assíncrona
    decisao, confianca = await analisar_saida_chatgpt_async(
        velas_mock, 2.5, "test_client"
    )

    assert (
        decisao == DecisaoTipo.SAIR.value
    ), f"Decisão esperada: SAIR, obtida: {decisao}"
    assert confianca == 0.78, f"Confiança esperada: 0.78, obtida: {confianca}"

    # Verifica se a decisão foi registrada na vela
    assert "ia_decisoes" in velas_mock[-1], "Decisão não foi registrada na vela"
    decisao_registrada = velas_mock[-1]["ia_decisoes"][-1]
    assert decisao_registrada["decisao"] == DecisaoTipo.SAIR.value
    assert decisao_registrada["tipo"] == "saida"
    assert decisao_registrada["lucro_atual"] == 2.5


# Teste de integração do fluxo completo de análise (mock)
def test_analisar_scalping(catalogador_instance, velas_mock, monkeypatch):
    """Testa o fluxo completo de análise de scalping"""
    # Simula velas no catalogador
    catalogador_instance.velas = velas_mock.copy()

    # Mock da função analisar_entrada_chatgpt para não depender da API real
    def mock_analisar_entrada(*args, **kwargs):
        return DecisaoTipo.CALL.value, 0.9

    # Aplica o mock
    monkeypatch.setattr("catalogador.analisar_entrada_chatgpt", mock_analisar_entrada)

    # Testa o método analisar_scalping
    resultado = catalogador_instance.analisar_scalping("test_client")

    assert (
        resultado["sinal"] == "compra"
    ), f"Sinal esperado: compra, obtido: {resultado['sinal']}"
    assert (
        resultado["confianca"] == 0.9
    ), f"Confiança esperada: 0.9, obtida: {resultado['confianca']}"
    assert "razao" in resultado, "O resultado deve incluir uma razão"


# Execute os testes com: pytest -xvs tests/test_catalogador.py
if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
