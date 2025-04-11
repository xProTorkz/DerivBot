from flask import render_template, request, jsonify, redirect, session
from motor import executar_operacao_sniper
import config
import os
import json
from datetime import datetime
from constantes import LICENCAS_PATH, LOGS_PATH
import websocket


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
                    lucro += dado["valor"] if dado["resultado"] == "lucro" else -abs(dado["valor"])
                    historico.append({
                        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "tipo": dado["resultado"],
                        "valor": dado["valor"],
                        "resultado": dado["valor"] if dado["resultado"] == "lucro" else -abs(dado["valor"])
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

