import websocket
import json

API_URL = "wss://ws.derivws.com/websockets/v3?app_id=71203"
ativo = "R_100"

# === Conexão com WebSocket ===
def conectar_ws():
    ws = websocket.WebSocket()
    ws.connect(API_URL)
    return ws

# === Autenticação com token ===
def autenticar(ws, token):
    ws.send(json.dumps({"authorize": token}))
    ws.recv()

# === Compra de contrato tipo MULTUP ou MULTDOWN ===
def comprar_contrato(valor, direcao="CALL", token=None):
    ws = conectar_ws()
    autenticar(ws, token)

    contract_type = "MULTUP" if direcao == "CALL" else "MULTDOWN"

    mensagem_compra = {
        "buy": 1,
        "price": valor,
        "parameters": {
            "amount": valor,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "symbol": ativo,
            "multiplier": 100  # ✅ valor aceito pela Deriv
        }
    }

    ws.send(json.dumps(mensagem_compra))
    resposta = json.loads(ws.recv())
    ws.close()

    if "error" in resposta:
        raise Exception("Erro ao comprar contrato: " + resposta["error"]["message"])

    return resposta["buy"]["contract_id"]


# === Verificação de lucro ===
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

    return resposta["proposal_open_contract"]["profit"]

# === Encerramento do contrato manual ===
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
