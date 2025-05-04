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
    safe_recv_json(ws)  # já ignora ou valida erros silenciosamente


# === Receber resposta do WebSocket de forma segura ===
def safe_recv_json(ws):
    raw = ws.recv()
    if not raw.strip():
        print("[⚠️ WS] Resposta vazia recebida.")
        return {}
    try:
        return json.loads(raw)
    except Exception as e:
        print(f"[⚠️ WS] Erro ao fazer parse do JSON: {e} | Conteúdo: {raw}")
        return {}


# === Compra de contrato MULTIPLIER ===
def comprar_contrato(valor, ativo="1HZ100V", token=None, multiplier=100):
    ws = conectar_ws()
    autenticar(ws, token)

    parametros = {
        "amount": valor,
        "basis": "stake",
        "contract_type": "MULTUP",  # Multiplier padrão de alta
        "symbol": ativo,
        "currency": "USD",
        "multiplier": multiplier,
    
    }

    mensagem_compra = {"buy": 1, "price": valor, "parameters": parametros}

    print(f"[DEBUG] Comprando MULTIPLIER: {json.dumps(mensagem_compra, indent=2)}")
    ws.send(json.dumps(mensagem_compra))
    resposta = safe_recv_json(ws)
    ws.close()

    if "error" in resposta:
        raise Exception("Erro ao comprar contrato: " + resposta["error"]["message"])

    return resposta["buy"]["contract_id"]


# === Verificação de lucro (usado para contratos em andamento) ===
def verificar_lucro(contract_id, token):
    ws = conectar_ws()
    autenticar(ws, token)

    ws.send(json.dumps({"proposal_open_contract": 1, "contract_id": contract_id}))
    resposta = safe_recv_json(ws)
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

    ws.send(
        json.dumps(
            {"sell": contract_id, "price": 0}  # aceita qualquer valor atual de venda
        )
    )
    resposta = safe_recv_json(ws)
    ws.close()

    if "error" in resposta:
        raise Exception("Erro ao encerrar contrato: " + resposta["error"]["message"])

    return resposta
