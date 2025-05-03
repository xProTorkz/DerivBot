import websocket
import json

def listar_ativos_multiplier():
    ws = websocket.create_connection("wss://ws.derivws.com/websockets/v3?app_id=71203")
    ws.send(json.dumps({
        "active_symbols": "full",

        "product_type": "basic"
    }))
    resposta = json.loads(ws.recv())
    ws.close()

    print("\n📋 JSON COMPLETO RECEBIDO DA API:\n")
    print(json.dumps(resposta, indent=2))


listar_ativos_multiplier()
