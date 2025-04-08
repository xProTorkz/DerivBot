
def log(msg):
    print(msg)
    if len(status_robo["logs"]) > 100:
        status_robo["logs"].pop(0)
    status_robo["logs"].append(msg)
# =============== INÍCIO DO CÓDIGO ===============
# Importando bibliotecas necessárias

import websocket
import json
import threading
import time
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

# === CONFIGURAÇÕES ===
TOKEN = "0hfU9DKnc0LnCZL"
VALOR_ENTRADA = 1
ATIVO = "R_100"
DURACAO = 5  # em segundos
TIPO_CONTRATO = "CALL"  # ou "PUT"
MODO_ATUAL = "iniciante"
status_robo = {
    "saldo": 0.0,
    "status": "Parado",
    "logs": []
}
buy_id = None  # ID da operação

# === STATUS DO ROBÔ (VISUALIZAÇÃO DO PAINEL) ===
# O status do robô é atualizado em tempo real na interface
status_robo = {"saldo": 0.0, "status": "Parado", "logs": []}

# === VARIÁVEIS ===
buy_id = None

def on_message(ws, message):
    global buy_id
    data = json.loads(message)

    if "error" in data:
        erro = data["error"].get("message", "Erro desconhecido.")
        log(f"❌ Erro recebido: {erro}")
        return

    if data.get("msg_type") == "authorize":
        conta = data["authorize"].get("account")
        tipo = "Conta Real" if conta.startswith("CR") else "Conta Demo"
        saldo = float(data["authorize"]["balance"])
        status_robo["saldo"] = saldo
        log(f"✅ Conectado na {tipo} | Saldo: R$ {saldo:.2f}")
        ws.send(json.dumps({"balance": 1, "account": "all"}))

    elif data.get("msg_type") == "balance":
        saldo = data["balance"]["balance"]
        status_robo["saldo"] = float(saldo)
        log(f"💰 Saldo atualizado: R$ {float(saldo):.2f}")

    elif data.get("msg_type") == "buy":
        buy_id = data["buy"]["buy_id"]
        log(f"📈 Operação enviada com sucesso | ID: {buy_id}")

    elif data.get("msg_type") == "proposal_open_contract":
        contract = data["proposal_open_contract"]
        if contract['is_sold']:
            lucro = contract['profit']
            resultado = "✅ WIN" if lucro > 0 else "❌ LOSS"
            log(f"🏁 Contrato finalizado: {resultado} | Lucro: R$ {lucro:.2f}")


def on_error(ws, error):
    print("[ERRO]", error)

def on_close(ws, close_status_code, close_msg):
    print(f"[🔌] Conexão encerrada. Código: {close_status_code} | Mensagem: {close_msg}")

def on_open(ws):
    log("🔐 Enviando token para autenticação...")
    auth_payload = json.dumps({"authorize": TOKEN})
    ws.send(auth_payload)

def iniciar_websocket():
    status_robo["status"] = "Conectando..."
    status_robo["logs"].append(f"🚀 Iniciando modo: {MODO_ATUAL}")

    ws = websocket.WebSocketApp(
        "wss://ws.derivws.com/websockets/v3",
        on_open=on_open,
        on_message=on_message,
        on_error=lambda ws, err: status_robo["logs"].append(f"❌ Erro de conexão: {err}"),
        on_close=lambda ws, code, msg: status_robo["logs"].append("🔌 Conexão encerrada.")
    )

    ws.run_forever()


if __name__ == "__main__":
    iniciar_websocket()
