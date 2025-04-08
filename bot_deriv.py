import websocket
import json
import threading
import time

# === CONFIGURAÇÕES ===
TOKEN = "0hfU9DKnc0LnCZL"
VALOR_ENTRADA = 1
ATIVO = "R_100"
DURACAO = 5  # em segundos
TIPO_CONTRATO = "CALL"  # ou "PUT"

# === STATUS DO ROBÔ (VISUALIZAÇÃO DO PAINEL) ===
# O status do robô é atualizado em tempo real na interface
status_robo = {"saldo": 0.0, "status": "Parado", "logs": []}

# === VARIÁVEIS ===
buy_id = None

def on_message(ws, message):
    global buy_id
    data = json.loads(message)

    if 'msg_type' in data:
        # Autorização (login com token)
        if data['msg_type'] == 'authorize':
            login_id = data['authorize']['loginid']
            print(f"[✔] Conectado como: {login_id}")
            status_robo["status"] = "Conectado e autenticado"
            status_robo["logs"].append(f"[🔐] Autenticado como: {login_id}")
            ws.send(json.dumps({"balance": 1, "account": "virtual"}))

        # Consulta de saldo
        elif data['msg_type'] == 'balance':
            saldo = data['balance']['balance'] / 100
            print(f"[💰] Saldo atual: ${saldo:.2f}")
            status_robo["saldo"] = saldo
            status_robo["status"] = "Pronto para operar"
            status_robo["logs"].append(f"[💰] Saldo atualizado: ${saldo:.2f}")
            iniciar_operacao(ws)

        # Confirmação de entrada
        elif data['msg_type'] == 'buy':
            buy_id = data['buy']['buy_id']
            print(f"[📈] Operação enviada! ID: {buy_id}")
            status_robo["logs"].append(f"[📈] Operação enviada! ID: {buy_id}")
            status_robo["status"] = "Contrato em andamento..."

        # Resultado do contrato
        elif data['msg_type'] == 'proposal_open_contract':
            contract = data['proposal_open_contract']
            if contract['is_sold']:
                lucro = contract['profit']
                resultado = "✅ WIN" if lucro > 0 else "❌ LOSS"
                print(f"[🏁] Contrato finalizado: {resultado} | Lucro: ${lucro:.2f}")
                status_robo["logs"].append(f"[🏁] {resultado} | Lucro: ${lucro:.2f}")
                status_robo["status"] = "Finalizado"
                ws.close()


def on_error(ws, error):
    print("[ERRO]", error)

def on_close(ws, close_status_code, close_msg):
    print(f"[🔌] Conexão encerrada. Código: {close_status_code} | Mensagem: {close_msg}")

def on_open(ws):
    token_payload = {
        "authorize": "0hfU9DKnc0LnCZL"  # Seu token da Deriv aqui
    }
    ws.send(json.dumps(token_payload))
    print("✅ Token enviado com sucesso!")
    print("[🔐] Autenticando...")
    ws.send(json.dumps({"authorize": TOKEN}))

def iniciar_operacao(ws):
    print(f"[🚀] Iniciando operação {TIPO_CONTRATO} em {ATIVO} por ${VALOR_ENTRADA} ({DURACAO}s)")
    buy_payload = {
        "buy": 1,
        "price": VALOR_ENTRADA,
        "parameters": {
            "amount": VALOR_ENTRADA,
            "basis": "stake",
            "contract_type": TIPO_CONTRATO,
            "currency": "USD",
            "duration": DURACAO,
            "duration_unit": "s",
            "symbol": ATIVO
        }
    }
    ws.send(json.dumps(buy_payload))

def iniciar_websocket():
    ws = websocket.WebSocketApp(
        r"wss://frontend.binaryws.com/websockets/v3",
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()
    while wst.is_alive():
        time.sleep(1)

if __name__ == "__main__":
    iniciar_websocket()
