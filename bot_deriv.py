
def log(msg):
    print(msg)
    if len(status_robo["logs"]) > 100:
        status_robo["logs"].pop(0)
    status_robo["logs"].append(msg)
# =============== INÍCIO DO CÓDIGO ===============
# Importando bibliotecas necessárias

import websocket
import json
import requests
import openai
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
ws_global = None

buy_id = None  # ID da operação
openai.api_key = "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"
# ID do seu assistant criado
ASSISTANT_ID = "asst_k2ak7MNpC92Mm2LrsywTs0x5"

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

        # ✅ Corrigido para evitar erro de NoneType
        if conta is not None:
            tipo = "Conta Real" if conta.startswith("CR") else "Conta Demo"
        else:
            tipo = "Conta desconhecida"

        saldo = float(data["authorize"]["balance"])
        status_robo["saldo"] = saldo
        log(f"✅ Conectado na {tipo} | Saldo: R$ {saldo:.2f}")

        # Solicita atualizações de saldo
        ws.send(json.dumps({"balance": 1, "account": "current"}))


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
    global ws_global
    status_robo["status"] = "Conectando..."
    status_robo["logs"].append(f"🚀 Iniciando modo: {MODO_ATUAL}")

    ws_global = websocket.WebSocketApp(
        "wss://ws.derivws.com/websockets/v3?app_id=71203",
        on_open=on_open,
        on_message=on_message,
        on_error=lambda ws, err: status_robo["logs"].append(f"❌ Erro de conexão: {err}"),
        on_close=lambda ws, code, msg: status_robo["logs"].append("🔌 Conexão encerrada.")
    )

    ws_global.run_forever()



def consultar_assistente(velas, saldo, meta, modo):
    """
    Envia os dados para o Assistant e retorna CALL, PUT ou AGUARDAR
    """

    try:
        # Monta a mensagem
        prompt = f"""
Dados de mercado:
Modo: {modo}
Saldo: {saldo}
Meta diária: {meta}
Velas recentes: {velas}

Com base nesses dados, o que o bot deve fazer agora?
Responda apenas: CALL, PUT ou AGUARDAR.
        """

        thread = openai.beta.threads.create()

        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt
        )

        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        # Aguarda o processamento terminar
        while True:
            status = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if status.status == "completed":
                break

        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        resposta = messages.data[0].content[0].text.value.strip().upper()

        if resposta in ["CALL", "PUT", "AGUARDAR"]:
            return resposta
        else:
            return "AGUARDAR"

    except Exception as e:
        print("Erro ao consultar assistente:", e)
        return "AGUARDAR"

def get_candles(ativo="R_100", quantidade=5, duration=1):
    try:
        response = requests.get(
            f"https://api.deriv.com/api/v1/ohlc/latest?symbol={ativo}&granularity={duration}"
        )
        data = response.json()
        candles = data['ohlc'][-quantidade:]
        return candles
    except Exception as e:
        log(f"Erro ao buscar velas: {e}")
        return []

# Envia ordem para a Deriv com base na decisão do Assistant
def enviar_ordem(tipo_contrato, valor):
    global ws_global
    if not ws_global:
        log("❌ WebSocket ainda não conectado.")
        return

    contrato = {
        "buy": 1,
        "price": valor,
        "parameters": {
            "amount": valor,
            "basis": "stake",
            "contract_type": tipo_contrato,
            "currency": "USD",
            "duration": 1,
            "duration_unit": "s",
            "symbol": ATIVO
        }
    }
    log(f"🟢 Enviando ordem: {tipo_contrato} | Valor: ${valor:.2f}")
    ws_global.send(json.dumps(contrato))


# Loop principal de operação
def loop_operacional():
    global VALOR_ENTRADA

    while True:
        saldo = status_robo["saldo"]
        if saldo <= 0:
            log("⚠️ Saldo insuficiente.")
            break

        # Define meta e valor de entrada baseado no modo
        meta = round(saldo * 0.1, 2)  # 10% do saldo
        if MODO_ATUAL == "agressivo":
            valor_entrada = round(meta * 0.2, 2)  # 20% da meta
        elif MODO_ATUAL == "conservador":
            valor_entrada = round(meta * 0.1, 2)
        else:
            valor_entrada = round(meta * 0.05, 2)  # iniciante

        VALOR_ENTRADA = max(valor_entrada, 0.35)  # mínimo aceitável

        velas = get_candles(ATIVO)

        if velas:
            decisao = consultar_assistente(velas, saldo, meta, MODO_ATUAL)

            if decisao in ["CALL", "PUT"]:
                enviar_ordem(decisao, VALOR_ENTRADA)
            else:
                log("🔎 IA recomendou aguardar...")

        time.sleep(2)  # aguarda 2s antes da próxima análise

if __name__ == "__main__":
    iniciar_websocket()
