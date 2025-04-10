from flask import Flask, render_template, request, jsonify, redirect, session
from motor import executar_operacao_sniper
import config
import os
import json
from datetime import datetime
from logs import LOGS_PATH
import websocket

app = Flask(__name__)
app.secret_key = "painel_deriv_seguro"  # Pode ajustar ou mover para .env depois

# === Função para pegar o saldo real da Deriv ===
def get_saldo(token):
    try:
        ws = websocket.WebSocket()
        ws.connect("wss://ws.derivws.com/websockets/v3?app_id=71287")
        ws.send(json.dumps({"authorize": token}))
        resposta = json.loads(ws.recv())
        ws.close()

        if "error" in resposta:
            raise Exception(resposta["error"]["message"])

        return resposta["authorize"]["balance"]

    except Exception as e:
        print(f"[ERRO SALDO] {e}")
        return 0.0

# === Painel com dados reais ===
@app.route("/painel")
def painel():
    if "token_deriv" not in session:
        return redirect("/")

    modo = config.MODO_ATUAL
    meta = config.MODOS[modo]["meta"]
    moeda = "USD"
    token = session.get("token_deriv")
    saldo = get_saldo(token)

    lucro = 0
    historico = []

    if os.path.exists(LOGS_PATH):
        with open(LOGS_PATH, "r") as f:
            for linha in f:
                if not linha.strip():
                    continue
                try:
                    dado = json.loads(linha)
                    lucro += dado["valor"] if dado["resultado"] == "lucro" else -abs(dado["valor"])
                    historico.append({
                        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "tipo": dado["resultado"],
                        "valor": dado["valor"],
                        "resultado": dado["valor"] if dado["resultado"] == "lucro" else -abs(dado["valor"])
                    })
                except:
                    continue

    return render_template("painel.html", saldo=saldo, lucro=lucro, meta=meta, moeda=moeda, historico=historico)

# === Rota para iniciar o robô ===
@app.route("/iniciar_bot", methods=["POST"])
def iniciar_bot():
    dados = request.get_json()
    modo = dados.get("modo")
    meta = float(dados.get("meta", 0))

    try:
        config.MODO_ATUAL = modo
        config.META_ATUAL = meta
        executar_operacao_sniper()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)})

# === Logout ===
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/")

# === Iniciar servidor ===
if __name__ == "__main__":
    app.run(debug=True)
