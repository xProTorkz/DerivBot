import websocket
import json
import time
import threading

API_URL = "wss://ws.derivws.com/websockets/v3?app_id=71203"

# === Conexão com WebSocket ===
def conectar_ws():
    ws = websocket.WebSocket()
    ws.connect(API_URL)
    return ws

# === Autenticação com token ===
def autenticar(ws, token):
    ws.send(json.dumps({"authorize": token}))
    ws.recv()

# === Compra de contrato tipo CALL ou PUT ===
def comprar_contrato(valor, ativo="R_100", direcao="CALL", token=None):
    ws = conectar_ws()
    autenticar(ws, token)

    parametros = {
        "amount": valor,
        "basis": "stake",          # valor fixo da entrada
        "contract_type": direcao,  # CALL ou PUT
        "currency": "USD",
        "duration": 60,            # duração em segundos (pode alterar)
        "duration_unit": "s",
        "symbol": ativo
    }

    mensagem_compra = {
        "buy": 1,
        "price": valor,
        "parameters": parametros
    }

    print(f"[DEBUG] Enviando compra com parâmetros: {json.dumps(mensagem_compra, indent=2)}")

    ws.send(json.dumps(mensagem_compra))
    resposta = json.loads(ws.recv())
    ws.close()

    if "error" in resposta:
        raise Exception("Erro ao comprar contrato: " + resposta["error"]["message"])

    return resposta["buy"]["contract_id"]

# === Verificação de lucro (usado para contratos em andamento) ===
def verificar_lucro(contract_id, token):
    ws = conectar_ws()
    autenticar(ws, token)

    ws.send(json.dumps({
        "proposal_open_contract": 1,
        "contract_id": contract_id
    }))
    resposta = json.loads(ws.recv())
    ws.close()

    if "error" in resposta:
        raise Exception("Erro ao verificar contrato: " + resposta["error"]["message"])

    contrato = resposta.get("proposal_open_contract", {})
    status = contrato.get("status")
    profit = contrato.get("profit")

    if status == "open" and profit is not None:
        return round(profit, 2)

    return -999  # contrato já foi encerrado

# === Encerramento manual (não necessário para CALL/PUT, mas mantido se quiser forçar encerramento) ===
def encerrar_contrato(contract_id, token):
    ws = conectar_ws()
    autenticar(ws, token)

    ws.send(json.dumps({
        "sell": contract_id,
        "price": 0
    }))
    resposta = json.loads(ws.recv())
    ws.close()

    if "error" in resposta:
        raise Exception("Erro ao encerrar contrato: " + resposta["error"]["message"])

    return resposta
