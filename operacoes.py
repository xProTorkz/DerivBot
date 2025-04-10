# operacoes.py

import websocket
import json
import threading
import time

API_URL = "wss://ws.derivws.com/websockets/v3?app_id=71203"
TOKEN = "FDWNvKWY67GtGKX"  # Substituir pelo token real

ativo = "R_10"
duracao = 5
barrier = None  # Não precisa para rise/fall

# Dado global do contrato em aberto
contrato_aberto = {
    "contract_id": None,
    "buy_price": 0,
    "profit": 0
}

# === CONEXÃO COM WEBSOCKET ===
def conectar_ws():
    ws = websocket.WebSocket()
    ws.connect(API_URL)
    return ws

# === AUTENTICAÇÃO ===
def autenticar(ws):
    ws.send(json.dumps({
        "authorize": TOKEN
    }))
    ws.recv()  # só pra confirmar

# === COMPRAR CONTRATO (CALL ou PUT) ===
def comprar_contrato(valor, direcao="CALL"):
    ws = conectar_ws()
    autenticar(ws)

    mensagem_compra = {
        "buy": 1,
        "price": valor,
        "parameters": {
            "amount": valor,
            "basis": "stake",
            "contract_type": direcao,  # "CALL" ou "PUT"
            "currency": "USD",
            "duration": duracao,
            "duration_unit": "s",
            "symbol": ativo
        }
    }

    ws.send(json.dumps(mensagem_compra))
    resposta = json.loads(ws.recv())

    if "error" in resposta:
        raise Exception("Erro ao comprar contrato: " + resposta["error"]["message"])

    contract_id = resposta["buy"]["contract_id"]
    ws.close()
    return contract_id

# === VERIFICAR LUCRO ===
def verificar_lucro(contract_id):
    ws = conectar_ws()
    autenticar(ws)

    mensagem = {
        "proposal_open_contract": 1,
        "contract_id": contract_id
    }

    ws.send(json.dumps(mensagem))
    resposta = json.loads(ws.recv())
    ws.close()

    if "error" in resposta:
        raise Exception("Erro ao verificar contrato: " + resposta["error"]["message"])

    return resposta["proposal_open_contract"]["profit"]

# === ENCERRAR CONTRATO ===
def encerrar_contrato(contract_id):
    ws = conectar_ws()
    autenticar(ws)

    mensagem = {
        "sell": contract_id,
        "price": 0  # vende pelo valor de mercado
    }

    ws.send(json.dumps(mensagem))
    resposta = json.loads(ws.recv())
    ws.close()

    if "error" in resposta:
        raise Exception("Erro ao encerrar contrato: " + resposta["error"]["message"])

    return resposta