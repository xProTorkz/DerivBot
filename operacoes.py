import websocket
import json
import time

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

# === Compra de contrato MULTIPLIER ===
def comprar_contrato(valor, ativo="1HZ100V", token=None, modo="iniciante"):

    ws = conectar_ws()
    autenticar(ws, token)
    multipliers = {
    "iniciante": 10,
    "conservador": 20,
    "agressivo": 100
    }


    parametros = {
        "amount": valor,
        "basis": "stake",
        "contract_type": "MULTUP",  # Multiplier padrão de alta
        "symbol": ativo,
        "currency": "USD",
        "multiplier": multipliers.get(modo, 50)  # multiplicador baseado no modo
        
    }

    mensagem_compra = {
        "buy": 1,
        "price": valor,
        "parameters": parametros
    }

    print(f"[DEBUG] Comprando MULTIPLIER: {json.dumps(mensagem_compra, indent=2)}")

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

# === Encerrar contrato manualmente (obrigatório no Multiplier para sair com lucro) ===
def encerrar_contrato(contract_id, token):
    ws = conectar_ws()
    autenticar(ws, token)

    ws.send(json.dumps({
        "sell": contract_id,
        "price": 0  # aceita qualquer valor atual de venda
    }))
    resposta = json.loads(ws.recv())
    ws.close()

    if "error" in resposta:
        raise Exception("Erro ao encerrar contrato: " + resposta["error"]["message"])

    return resposta
