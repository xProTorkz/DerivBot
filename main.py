import os
import json
import uuid
import config
from motor import estado, executar_operacao_sniper
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, jsonify
from flask_cors import CORS
from constantes import LICENCAS_PATH, LOGS_PATH
from app import painel, lucro_meta, historico_completo, get_saldo, trocar_conta, status_deriv, toggle_bot, status_robo_route, historico_resultados



app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "segredo_super_top_do_lucas")
# ROTAS PÚBLICAS (acesso antes do painel)

# if estado["robo_ativo"]:
#    print("⏪ Reiniciando robô automaticamente...")
#    iniciar_robo_em_thread(estado["modo"], estado["token"], estado["meta"], estado["tipo_conta"])
# Resetar o status.json ao iniciar o servidor
if not config.status_robo():
    with open("status.json", "w") as f:
        json.dump({
            "robo_ativo": False,
            "lucro": 0,
            "meta": 0
        }, f, indent=2)

estado = {
    "robo_ativo": False,
    "modo": None,
    "token": None,
    "meta": 0,
    "tipo_conta": None,
    "lucro_total": 0  # <- ESSENCIAL
}

# ROTAS PROTEGIDAS (painel e funções)
app.add_url_rule("/painel", "painel", painel)


# ROBÔ / API
app.add_url_rule("/toggle_bot", "toggle_bot", toggle_bot, methods=["POST"])
app.add_url_rule("/status_robo", "status_robo", status_robo_route, methods=["GET"])
app.add_url_rule("/executar_operacao_sniper", "executar_operacao_sniper", executar_operacao_sniper, methods=["POST"])
app.add_url_rule("/get_saldo", "get_saldo", get_saldo, methods=["GET"])
app.add_url_rule("/status_deriv", "status_deriv", status_deriv)
app.add_url_rule("/trocar_conta", "trocar_conta", trocar_conta, methods=["POST"])
app.add_url_rule("/historico_resultados", "historico_resultados", historico_resultados, methods=["GET"])
app.add_url_rule("/lucro_meta", "lucro_meta", lucro_meta, methods=["GET"])
app.add_url_rule("/historico_completo", "historico_completo", historico_completo, methods=["GET"])

def get_ip():
    return request.remote_addr

def get_hwid():
    return str(hex(uuid.getnode()))

@app.route("/")
def home():
    if "token_deriv" in session:
        return redirect("/painel")
    return redirect("/login")

@app.route("/login")
def login():
    ip = get_ip()
    hwid = get_hwid()

    # Nenhum arquivo de licença? Redireciona pro login comum
    if not os.path.exists(LICENCAS_PATH):
        return render_template("login.html")

    with open(LICENCAS_PATH, "r") as f:
        licencas = json.load(f)

    for chave, licenca in licencas.items():
        # Verifica se o IP ou HWID batem
        if ip in licenca.get("ips", []) or hwid in licenca.get("hwids", []):
            session["chave_ativacao"] = chave

            # Verifica qual conta está ativa
            if licenca.get("token_real"):
                session["token_deriv"] = licenca["token_real"]
                session["email"] = licenca["deriv_real"]
                session["tipo_conta"] = "real"
                return redirect("/painel")

            elif licenca.get("token_demo"):
                session["token_deriv"] = licenca["token_demo"]
                session["email"] = licenca["deriv_demo"]
                session["tipo_conta"] = "demo"
                return redirect("/painel")

    # Se nenhuma licença com IP ou HWID foi encontrada, mostra o login normal
    return render_template("login.html")

@app.route("/ativar")
def ativar():
    chave = request.args.get("chave")
    return redirect(f"/login?chave={chave}")

@app.route("/validar_token")
def validar_token():
    import websocket

    token = request.args.get("token1")
    ip = get_ip()
    hwid = get_hwid()

    if not token:
        return render_template("acesso_negado.html", erro="Token não informado."), 400

    chave = session.get("chave_ativacao")
    if not chave or not os.path.exists(LICENCAS_PATH):
        return render_template("acesso_negado.html", erro="Chave de ativação inválida ou não encontrada."), 403

    with open(LICENCAS_PATH, "r") as f:
        licencas = json.load(f)

    licenca = licencas.get(chave)
    if not licenca:
        return render_template("acesso_negado.html", erro="Licença não encontrada."), 403

    # 📡 Detecta tipo de conta via WebSocket da Deriv
    try:
        ws = websocket.WebSocket()
        ws.connect("wss://ws.derivws.com/websockets/v3?app_id=71287")
        ws.send(json.dumps({"authorize": token}))
        resposta = json.loads(ws.recv())
        ws.close()

        if "error" in resposta:
            return render_template("acesso_negado.html", erro="❌ Token inválido ou expirado."), 403

        conta = resposta["authorize"]["loginid"]
        tipo_conta = "demo" if conta.startswith("VRTC") else "real"

    except Exception as e:
        print(f"[ERRO TOKEN] {e}")
        return render_template("acesso_negado.html", erro="Erro ao validar token com a Deriv."), 500

    # 🛡️ Garante estrutura mínima
    for campo in ["demo", "real"]:
        licenca.setdefault(f"token_{campo}", "")
        licenca.setdefault(f"deriv_{campo}", "")
        licenca.setdefault(f"ativado_em_{campo}", "")
    licenca.setdefault("ips", [])
    licenca.setdefault("hwids", [])

    # 🚫 Já ativou esse tipo de conta?
    if licenca[f"token_{tipo_conta}"]:
        return render_template("acesso_negado.html", erro=f"⚠️ Esta chave já foi usada para ativar uma conta {tipo_conta.upper()}."), 403

    # 🔐 Bloqueia ativação de um novo tipo de conta por outro dispositivo
    dispositivo_registrado = ip in licenca["ips"] or hwid in licenca["hwids"]
    ja_usou_outro_tipo = licenca["token_demo"] or licenca["token_real"]

    if ja_usou_outro_tipo and not dispositivo_registrado:
        return render_template("acesso_negado.html", erro="🚫 Este dispositivo/IP não está autorizado para usar esta chave."), 403

    # 💾 Registra dados
    if ip not in licenca["ips"]:
        licenca["ips"].append(ip)
    if hwid not in licenca["hwids"]:
        licenca["hwids"].append(hwid)

    licenca[f"token_{tipo_conta}"] = token
    licenca[f"deriv_{tipo_conta}"] = conta
    licenca[f"ativado_em_{tipo_conta}"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(LICENCAS_PATH, "w") as f:
        json.dump(licencas, f, indent=2)

    # 🧠 Seta sessão
    session.permanent = True
    session["token_deriv"] = token
    session["email"] = conta
    session["tipo_conta"] = tipo_conta

    return redirect("/configuracao")

@app.route("/configuracao", methods=["GET", "POST"])
def configuracao():
    if "token_deriv" not in session:
        return redirect("/login")

    if request.method == "POST":
        aceite = request.form.get("aceite")
        tipo_conta = request.form.get("tipo_conta")

        if not aceite or not tipo_conta:
            return render_template("configuracao.html", erro="Marque o tipo de conta e aceite os termos.")

        session["tipo_conta"] = tipo_conta
        return redirect("/painel")

    return render_template("configuracao.html")

@app.route("/saldo_atual")
def saldo_atual():
    if "token_deriv" not in session:
        return jsonify({"status": "erro", "mensagem": "Token não encontrado."})

    try:
        saldo = get_saldo(session["token_deriv"])
        return jsonify({"status": "ok", "saldo": saldo})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)})

@app.route("/limpar_historico", methods=["POST"])
def limpar_historico():
    try:
        open("data/logs.txt", "w").close()  # limpa o arquivo
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)})

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
