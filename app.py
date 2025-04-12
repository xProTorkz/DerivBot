from flask import render_template, request, jsonify, redirect, session
from motor import executar_operacao_sniper
from config import iniciar_robo, status_robo, parar_robo
import config
import os
import json
from datetime import datetime
from constantes import LICENCAS_PATH, LOGS_PATH
import websocket
import threading


robos_em_execucao = {}

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


def painel():
    if "token_deriv" not in session or "tipo_conta" not in session:
        return redirect("/")

    chave = session.get("chave_ativacao")
    if not chave or not os.path.exists(LICENCAS_PATH):
        return redirect("/")

    with open(LICENCAS_PATH, "r") as f:
        licencas = json.load(f)

    licenca = licencas.get(chave)
    if not licenca:
        return render_template("acesso_negado.html"), 403

    tipo_conta = session.get("tipo_conta")
    conta_id = licenca.get(f"deriv_{tipo_conta}", "----")
    ativado_em = licenca.get(f"ativado_em_{tipo_conta}", "--/--/----")

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
                    lucro += dado.get("resultado_real", 0)
                    historico.append({
                        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "tipo": dado["resultado"],
                        "valor": dado["valor"],  # valor da entrada
                        "resultado_real": dado.get("resultado_real", 0)
                    })

                except:
                    continue

    return render_template(
        "painel.html",
        saldo=saldo,
        lucro=lucro,
        meta=meta,
        moeda=moeda,
        historico=historico,
        tipo_conta=tipo_conta,
        conta_id=conta_id,
        chave=chave,
        ativado_em=ativado_em
    )


def configuracao():
    if request.method == "POST":
        token = request.form.get("token")
        tipo_conta = request.form.get("tipo_conta")
        aceite = request.form.get("aceite")
        chave = session.get("chave_ativacao")

        if not token or not tipo_conta or not aceite:
            return "Preencha todos os campos obrigatórios!", 400

        try:
            ws = websocket.WebSocket()
            ws.connect("wss://ws.derivws.com/websockets/v3?app_id=71287")
            ws.send(json.dumps({"authorize": token}))
            resposta = json.loads(ws.recv())
            ws.close()

            if "error" in resposta:
                return "Token inválido ou expirado!", 401

            session["token_deriv"] = token
            session["tipo_conta"] = tipo_conta
            session["chave_ativacao"] = chave

            print(f"✅ Token autorizado com sucesso para chave: {chave}")
            return redirect("/painel")

        except Exception as e:
            print(f"[ERRO AUTORIZAÇÃO]: {e}")
            return "Erro ao validar o token. Tente novamente.", 500

    chave = session.get("chave_ativacao")
    return render_template("configuracao.html", chave=chave)

def trocar_conta():
    if "chave_ativacao" not in session:
        return redirect("/login")

    chave = session["chave_ativacao"]

    if not os.path.exists(LICENCAS_PATH):
        return redirect("/login")

    with open(LICENCAS_PATH, "r") as f:
        licencas = json.load(f)

    licenca = licencas.get(chave)
    if not licenca:
        return redirect("/login")

    if session["tipo_conta"] == "demo" and licenca.get("token_real"):
        session["token_deriv"] = licenca["token_real"]
        session["email"] = licenca["deriv_real"]
        session["tipo_conta"] = "real"

    elif session["tipo_conta"] == "real" and licenca.get("token_demo"):
        session["token_deriv"] = licenca["token_demo"]
        session["email"] = licenca["deriv_demo"]
        session["tipo_conta"] = "demo"

    return redirect("/painel")

    
def status_deriv():
    import websocket
    import json

    if "token_deriv" not in session:
        return jsonify({"status": "erro", "mensagem": "Token não encontrado."})

    try:
        ws = websocket.WebSocket()
        ws.connect("wss://ws.derivws.com/websockets/v3?app_id=71287")
        ws.send(json.dumps({"authorize": session["token_deriv"]}))
        resposta = json.loads(ws.recv())
        ws.close()

        if "authorize" in resposta:
            return jsonify({"status": "ok"})
        else:
            return jsonify({"status": "erro", "mensagem": "Token inválido ou expirado."})

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)})


    return redirect("/painel")


# ========== ROTAS ========

def status_robo_route():
    return jsonify({"ativo": status_robo()})


def toggle_bot():
    if status_robo():
        parar_robo()
        return jsonify({"status": "parado"})
    else:
        config.iniciar_robo()  # <- adiciona essa linha
        print("⚙️ Iniciando robô em thread...")

        modo = config.MODO_ATUAL  # ou você pode puxar do session, se preferir
        token = session.get("token_deriv")
        meta = config.MODOS[modo]["meta"]
        tipo_conta = session.get("tipo_conta")

        thread = threading.Thread(
            target=executar_operacao_sniper,
            args=(modo, token, meta, tipo_conta)
        )

        thread.daemon = True  # Pra encerrar junto com o app
        thread.start()

        return jsonify({"status": "iniciado"})
    
    
def historico_resultados():
    if not os.path.exists(LOGS_PATH):
        return jsonify([])

    historico = []

    with open(LOGS_PATH, "r") as f:
        for linha in f:
            if not linha.strip():
                continue
            try:
                dado = json.loads(linha)
                historico.append({
                    "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "tipo": dado["resultado"],
                    "valor": dado["valor"],
                    "resultado_real": dado.get("resultado_real", 0)
                })

            except:
                continue

    return jsonify(historico)

