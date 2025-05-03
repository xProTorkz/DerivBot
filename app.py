from flask import render_template, request, jsonify, redirect, session
from motor import executar_operacao_sniper, estado
from config import iniciar_robo, status_robo
from threading import Thread
import config
import os
import json
from datetime import datetime
from constantes import LICENCAS_PATH, LOGS_PATH
import websocket

thread_robo = None
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

    # Usar o modo padrão (não tentar pegar do request!)
    modo = config.MODO_ATUAL
    meta = config.MODOS[modo]["meta"]
    moeda = "USD"
    token = session.get("token_deriv")
    saldo = get_saldo(token)

    lucro = 0
    historico = []

    if status_robo() and os.path.exists(LOGS_PATH):
        with open(LOGS_PATH, "r") as f:
            for linha in f:
                if not linha.strip():
                    continue
                try:
                    dado = json.loads(linha)

                    # 🛠️ Corrige resultado_real se for prejuízo e estiver zerado
                    if dado.get("resultado") == "prejuízo" and float(dado.get("resultado_real", 0)) == 0:
                        dado["resultado_real"] = -float(dado.get("valor", 0))

                    valor = round(float(dado.get("valor", 0)), 2)
                    resultado_real = round(float(dado.get("resultado_real", 0)), 2)

                    saldo_inicial = carregar_status().get("saldo_inicial", saldo)  # usar o saldo salvo na hora de iniciar o robô
                    lucro = round(saldo - saldo_inicial, 2)


                    historico.append({
                        "data": dado.get("data", datetime.now().strftime("%Y-%m-%d")),
                        "hora": dado.get("hora", datetime.now().strftime("%H:%M:%S")),
                        "tipo": dado.get("tipo", dado.get("resultado", "--")),
                        "valor": valor,
                        "resultado_real": resultado_real
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
        ativado_em=ativado_em,
        validade=ativado_em
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

# ========== ROTAS ========

def lucro_meta():
    try:
        with open("status.json", "r") as f:
            dados = json.load(f)
        return jsonify({
            "status": "ok",
            "lucro": float(dados.get("lucro", 0)),
            "meta": float(dados.get("meta", 0))
        })
    except Exception as e:
        print(f"[ERRO LUCRO META] {e}")
        return jsonify({
            "status": "erro",
            "lucro": 0,
            "meta": 0
        })

def status_robo_route():
    return jsonify({"ativo": status_robo()})

def limpar_arquivo_historico():
    try:
        open("data/logs.txt", "w").close()
        print("🧹 Histórico limpo.")
    except:
        print("⚠️ Erro ao limpar histórico.")

def toggle_bot():
    global estado

    data = request.get_json()
    modo = data.get("modo")
    meta = float(data.get("meta"))
    token = session.get("token_deriv")
    tipo_conta = session.get("tipo_conta")

    if not config.ROBO_ATIVO:
        limpar_arquivo_historico()
        saldo_atual = get_saldo(token)
        salvar_status_inicial(saldo_atual, 0, meta)
        iniciar_robo_em_thread(modo, token, meta, tipo_conta)
        return jsonify({"status": "iniciado"})

    else:
        config.ROBO_ATIVO = False
        return jsonify({"status": "parado"})   
    
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
                print(f"[DEBUG LOG] Resultado Real Lido: {dado.get('resultado_real')} | Tipo: {dado.get('resultado')}")

                valor = round(float(dado.get("valor", 0)), 2)
                resultado_real = round(float(dado.get("resultado_real", 0)), 2)

                historico.append({
                    "data": dado.get("data", "--"),
                    "hora": dado.get("hora", "--"),
                    "tipo": dado.get("resultado", "--"),
                    "valor": valor,
                    "resultado_real": resultado_real
                })

            except Exception as e:
                print(f"Erro ao processar linha do log: {e}")
                continue

    return jsonify(historico)

def iniciar_robo_em_thread(modo, token, meta, tipo_conta):
    global thread_robo
    thread_robo = Thread(target=executar_operacao_sniper, args=(modo, token, meta, tipo_conta))
    thread_robo.daemon = True  # roda em segundo plano
    thread_robo.start()

def carregar_status():
    try:
        with open("status.json", "r") as f:
            return json.load(f)
    except:
        return {"robo_ativo": False}

def salvar_status(lucro_total, meta):
    try:
        status_path = "status.json"

        dados = {
            "robo_ativo": True,
            "lucro": float(round(lucro_total, 2)),
            "meta": float(round(meta, 2))
        }

        with open(status_path, "w") as f:
            json.dump(dados, f, indent=2)

        print(f"[✔️ STATUS SALVO] Lucro acumulado: ${dados['lucro']} | Meta: ${dados['meta']}")
    except Exception as e:
        print(f"[ERRO AO SALVAR STATUS] {e}")

def salvar_status_inicial(saldo_inicial, lucro_total, meta):
    with open("status.json", "w") as f:
        json.dump({
            "robo_ativo": True,
            "saldo_inicial": round(saldo_inicial, 2),
            "lucro": round(lucro_total, 2),
            "meta": round(meta, 2)
        }, f, indent=2)

# ========== HISTÓRICO ========

def historico_completo():
    if not os.path.exists(LOGS_PATH):
        return render_template("historico_completo.html", historico=[], resumo={})

    historico = []
    total_operacoes = 0
    total_lucros = 0
    total_prejuizos = 0
    total_valor_lucro = 0.0
    total_valor_prejuizo = 0.0

    with open(LOGS_PATH, "r") as f:
        for linha in f:
            if not linha.strip():
                continue
            try:
                dado = json.loads(linha)
                valor = round(float(dado.get("valor", 0)), 2)
                resultado_real = round(float(dado.get("resultado_real", 0)), 2)
                tipo = dado.get("resultado", "--")
                modo = dado.get("modo", "--")
                data = dado.get("data", "--")
                hora = dado.get("hora", "--")

                historico.append({
                    "data": data,
                    "hora": hora,
                    "modo": modo,
                    "tipo": tipo,
                    "valor": valor,
                    "resultado_real": resultado_real
                })

                total_operacoes += 1
                if resultado_real >= 0:
                    total_lucros += 1
                    total_valor_lucro += resultado_real
                else:
                    total_prejuizos += 1
                    total_valor_prejuizo += resultado_real

            except Exception as e:
                print(f"Erro no parse do log: {e}")
                continue

    assertividade = round((total_lucros / total_operacoes) * 100, 2) if total_operacoes > 0 else 0
    resumo = {
        "total": total_operacoes,
        "lucros": total_lucros,
        "prejuizos": total_prejuizos,
        "assertividade": assertividade,
        "total_lucro": round(total_valor_lucro, 2),
        "total_prejuizo": round(total_valor_prejuizo, 2),
        "saldo_final": round(total_valor_lucro + total_valor_prejuizo, 2)
    }

    historico.reverse()  # mais recente primeiro
    return render_template("historico_completo.html", historico=historico, resumo=resumo)