#!/usr/bin/env python
# -*- coding: utf-8 -*-
# main.py - Versão completa com integração ao painel e API JS + controle de lucro/meta/histórico
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    flash,
    send_from_directory,
)
from app import App
import config
import os
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
from motor import Motor
import admin  # Importa o módulo de administração
import sys
import uuid
import string
import re
import requests
import traceback

load_dotenv()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
ADMIN_TOKEN_DEMO = os.getenv("ADMIN_TOKEN_DEMO")
ADMIN_TOKEN_REAL = os.getenv("ADMIN_TOKEN_REAL")
ADMIN_DERIV_DEMO = os.getenv("ADMIN_DERIV_DEMO")
ADMIN_DERIV_REAL = os.getenv("ADMIN_DERIV_REAL")

app = Flask(__name__, template_folder="templates")
# Gera chave secreta estática (para persistir cookies entre reinícios) ou lê do .env
app.secret_key = os.getenv("FLASK_SECRET_KEY", "minha_chave_flask_super_secreta")


# Rota para servir arquivos da pasta img
@app.route("/img/<path:filename>")
def serve_image(filename):
    return send_from_directory(os.path.join(os.getcwd(), "img"), filename)


trading_app = App()
meta_diaria = config.TAKE_PROFIT


@app.route("/")
def painel():
    if "email" not in session:
        return redirect(url_for("login"))

    # Código de depuração
    print("DEBUG - Carregando página do painel")
    print(f"DEBUG - Email: {session.get('email')}")
    print(f"DEBUG - Código de licença da sessão: {session.get('codigo_licenca')}")
    print(f"DEBUG - Plano: {session.get('plano')}")

    # Recupera o token salvo na sessão
    token = session.get("token")

    # Conecta o motor global da aplicação se ainda não estiver conectado ou se o token mudou
    if token and (not trading_app.motor.conectado or trading_app.motor.token != token):
        # Garante que qualquer conexão anterior seja encerrada
        trading_app.motor.desconectar()
        trading_app.motor.conectar(token)

    # Obter informações da licença da sessão
    codigo_licenca = session.get("codigo_licenca", "")
    plano = session.get("plano", "free")

    return render_template(
        "painel.html",
        email=session.get("email", "demo@deriv.com"),
        tipo_conta=session.get("tipo_conta", "demo"),
        validade=session.get("validade", "N/A"),
        saldo=trading_app.motor.obter_saldo(),
        moeda="USD",
        historico=trading_app.obter_historico(),
        codigo_licenca=codigo_licenca,
        plano=plano,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")

        # Aqui você implementaria a validação real
        if email and senha:
            session["email"] = email
            session["tipo_conta"] = "demo"  # ou "real"
            session["validade"] = "2025-12-31"
            return redirect(url_for("painel"))

    return render_template("login.html")


@app.route("/login_token", methods=["GET", "POST"])
def login_token():
    ip = request.remote_addr
    hwid = get_hwid()
    licenca = buscar_licenca_por_ip_ou_hwid(ip, hwid)

    if licenca:
        # Sessão automática
        session["email"] = licenca["email"]
        session["token"] = licenca["token"]
        session["tipo_conta"] = licenca.get("tipo_conta", "demo")
        session["deriv_account"] = licenca.get("deriv_account", "")
        return redirect("/")

    if request.method == "POST":
        token = request.form.get("token")
        licencas = carregar_licencas()
        for key, lic in licencas.items():
            if lic["token"] == token:
                # Atualiza IP/HWID na licença
                if ip not in lic.get("ips", []):
                    lic.setdefault("ips", []).append(ip)
                if hwid not in lic.get("hwids", []):
                    lic.setdefault("hwids", []).append(hwid)
                with open("data/licencas.json", "w", encoding="utf-8") as f:
                    json.dump(licencas, f, indent=2, ensure_ascii=False)
                # Sessão
                session["email"] = lic["email"]
                session["token"] = lic["token"]
                session["tipo_conta"] = lic.get("tipo_conta", "demo")
                session["deriv_account"] = lic.get("deriv_account", "")
                return redirect("/")
        # Token inválido
        return render_template("login.html", erro="Token inválido ou não licenciado.")

    return render_template("login.html")


@app.route("/toggle_bot", methods=["POST"])
def toggle_bot():
    global meta_diaria
    dados = request.get_json()
    modo = dados.get("modo", "iniciante")
    meta = float(dados.get("meta", config.TAKE_PROFIT))
    meta_diaria = meta

    # Obtém token da sessão para uso no robô
    token = session.get("token")

    if trading_app.rodando:
        trading_app.parar()
        return jsonify({"status": "parado"})
    else:
        if trading_app.iniciar(token, modo, meta):
            return jsonify({"status": "iniciado", "modo": modo, "meta": meta})
        return jsonify({"status": "erro", "mensagem": "Falha ao iniciar robô"})


@app.route("/status_robo")
def status_robo():
    status = trading_app.status()
    return jsonify(
        {
            "ativo": trading_app.rodando,
            "operacoes": status["operacoes_realizadas"],
            "lucro": status["lucro_sessao"],
            "saldo": status["saldo_atual"],
            "tempo": status["tempo_execucao"],
        }
    )


@app.route("/status_detalhado")
def status_detalhado():
    """Endpoint para retornar status detalhado com logs personalizados e estado da operação."""
    status = trading_app.status()
    return jsonify(
        {
            "ativo": status["rodando"],
            "operacoes": status["operacoes_realizadas"],
            "operacoes_ativas": status["operacoes_ativas"],
            "lucro": status["lucro_sessao"],
            "saldo": status["saldo_atual"],
            "meta": status["meta_diaria"],
            "meta_progresso": status["meta_progresso"],
            "modo": status["modo"],
            "status_operacao": status["status_operacao"],
            "mensagem_log": status["ultimo_log"],
        }
    )


@app.route("/status_deriv")
def status_deriv():
    status_flag = "ok" if trading_app.motor.conectado else "erro"
    return jsonify({"status": status_flag, "mensagem": trading_app.motor.ultimo_erro})


@app.route("/saldo_atual")
def saldo_atual():
    return jsonify({"status": "ok", "saldo": trading_app.motor.obter_saldo()})


@app.route("/lucro_meta")
def lucro_meta():
    return jsonify(
        {"status": "ok", "lucro": trading_app.lucro_sessao, "meta": meta_diaria}
    )


@app.route("/historico_resultados")
def historico_resultados():
    resultado = []
    for op in trading_app.motor.historico_operacoes:
        resultado.append(
            {
                "data": op.get("timestamp_abertura", "--").split(" ")[0],
                "hora": op.get("timestamp_abertura", "--").split(" ")[-1],
                "tipo": op.get("tipo", "--"),
                "valor": op.get("preco_entrada", 0),
                "resultado_real": op.get("lucro", 0),
            }
        )
    return jsonify(resultado)


@app.route("/limpar_historico", methods=["POST"])
def limpar_historico():
    trading_app.motor.historico_operacoes = []
    return jsonify({"status": "ok"})


@app.route("/trocar_conta", methods=["POST"])
def trocar_conta():
    try:
        # Para o robô se estiver rodando
        if trading_app.rodando:
            trading_app.parar()

        # Limpa a sessão
        session.clear()

        # Redireciona para a página de login
        return redirect(url_for("login"))
    except Exception as e:
        print(f"[ERROR] Erro ao trocar conta: {str(e)}")
        return jsonify({"status": "erro", "mensagem": "Erro ao trocar conta"})


@app.route("/logout", methods=["POST"])
def logout():
    trading_app.parar()
    session.clear()
    return jsonify({"status": "desconectado"})


def carregar_licencas():
    path = "data/licencas.json"
    if not os.path.exists("data"):
        os.makedirs("data")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("{}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_hwid():
    # Exemplo simples, pode ser aprimorado
    return hex(uuid.getnode())


def buscar_licenca_por_ip_ou_hwid(ip, hwid):
    licencas = carregar_licencas()
    for lic in licencas.values():
        if ip in lic.get("ips", []) or hwid in lic.get("hwids", []):
            return lic
    # Se não encontrar, verifica se é o admin pelo .env
    if ip == "127.0.0.1" or hwid in ["0x22334d051b1a"]:
        return {
            "email": ADMIN_EMAIL,
            "token": ADMIN_TOKEN,
            "token_demo": ADMIN_TOKEN_DEMO,
            "token_real": ADMIN_TOKEN_REAL,
            "deriv_demo": ADMIN_DERIV_DEMO,
            "deriv_real": ADMIN_DERIV_REAL,
            "tipo_conta": "admin",
        }
    return None


@app.route("/ativacao", methods=["GET", "POST"])
def ativacao():
    erro = None
    if request.method == "POST":
        try:
            codigo_licenca = request.form.get("codigo_licenca", "").strip()
            token_demo = request.form.get("token_deriv_demo", "").strip()
            token_real = request.form.get("token_deriv_real", "").strip()
            aceite = request.form.get("aceite")

            print(f"[DEBUG] Código: {codigo_licenca}")
            print(f"[DEBUG] Token Demo: {token_demo}")
            print(f"[DEBUG] Token Real: {token_real}")
            print(f"[DEBUG] Aceite: {aceite}")

            if not codigo_licenca:
                erro = "❌ Código de licença não informado."
                return render_template("login.html", erro=erro)

            if not aceite:
                erro = "❌ Você precisa aceitar os termos para continuar."
                return render_template("login.html", erro=erro)

            if not token_demo and not token_real:
                erro = "❌ Você precisa fornecer pelo menos um token da Deriv (demo ou real)."
                return render_template("login.html", erro=erro)

            ip = request.remote_addr
            hwid = get_hwid()
            licencas = carregar_licencas()

            print(f"[DEBUG] IP: {ip}")
            print(f"[DEBUG] HWID: {hwid}")
            print(f"[DEBUG] Licenças: {licencas}")

            licenca_encontrada = False
            for key, lic in licencas.items():
                if lic.get("codigo_licenca") == codigo_licenca:
                    licenca_encontrada = True
                    print(f"[DEBUG] Licença encontrada: {key}")

                    # Salva IP/HWID
                    if ip not in lic.get("ips", []):
                        lic.setdefault("ips", []).append(ip)
                    if hwid not in lic.get("hwids", []):
                        lic.setdefault("hwids", []).append(hwid)

                    # Salva tokens se enviados
                    if token_demo:
                        lic["token_deriv_demo"] = token_demo
                    if token_real:
                        lic["token_deriv_real"] = token_real

                    # Atualiza status para 'ativa' se estava como 'gerada'
                    if lic.get("status") == "gerada":
                        lic["status"] = "ativa"
                        lic["ativado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")

                    # Salva alterações
                    with open("data/licencas.json", "w", encoding="utf-8") as f:
                        json.dump(licencas, f, indent=2, ensure_ascii=False)

                    # Configura sessão
                    session["codigo_licenca"] = codigo_licenca
                    session["licenca_id"] = key
                    session["plano"] = lic.get("plano", "free")
                    session["validade"] = lic.get("validade", "N/A")

                    # Verifica tokens
                    token_demo_final = lic.get("token_deriv_demo")
                    token_real_final = lic.get("token_deriv_real")

                    print(f"[DEBUG] Token Demo Final: {token_demo_final}")
                    print(f"[DEBUG] Token Real Final: {token_real_final}")

                    if token_real_final or token_demo_final:
                        if token_real_final:
                            session["token"] = token_real_final
                            session["tipo_conta"] = "real"
                        else:
                            session["token"] = token_demo_final
                            session["tipo_conta"] = "demo"

                        session["token_deriv_demo"] = token_demo_final
                        session["token_deriv_real"] = token_real_final
                        session["email"] = lic.get("email", "")

                        print("[DEBUG] Redirecionando para o painel...")
                        return redirect(url_for("painel"))
                    else:
                        erro = "❌ Você precisa cadastrar pelo menos um token da Deriv para continuar."
                        return render_template("login.html", erro=erro)

            if not licenca_encontrada:
                erro = "❌ Licença inválida ou não encontrada."
                return render_template("login.html", erro=erro)

        except Exception as e:
            print(f"[ERROR] Erro na ativação: {str(e)}")
            erro = f"❌ Erro ao processar ativação: {str(e)}"
            return render_template("login.html", erro=erro)

    # Se chegou aqui, é GET ou erro não tratado
    return render_template("login.html", erro=erro)


@app.route("/cadastrar_token", methods=["GET", "POST"])
def cadastrar_token():
    erro = request.args.get("erro")
    if "licenca_id" not in session:
        return redirect("/ativacao")
    if request.method == "POST":
        token_demo = request.form.get("token_deriv_demo")
        token_real = request.form.get("token_deriv_real")
        licencas = carregar_licencas()
        lic = licencas[session["licenca_id"]]
        if token_demo:
            lic["token_deriv_demo"] = token_demo
        if token_real:
            lic["token_deriv_real"] = token_real
        with open("data/licencas.json", "w", encoding="utf-8") as f:
            json.dump(licencas, f, indent=2, ensure_ascii=False)
        # Decide tipo de conta automaticamente
        if token_real:
            session["token"] = token_real
            session["tipo_conta"] = "real"
        elif token_demo:
            session["token"] = token_demo
            session["tipo_conta"] = "demo"
        else:
            return render_template(
                "cadastrar_token.html",
                erro="Você precisa cadastrar pelo menos um token da Deriv para continuar.",
            )
        session["token_deriv_demo"] = token_demo
        session["token_deriv_real"] = token_real
        session["email"] = lic.get("email", "")
        return redirect("/")
    return render_template("cadastrar_token.html", erro=erro)


@app.route("/conectar_demo", methods=["POST"])
def conectar_demo():
    token_demo = session.get("token_deriv_demo")
    if token_demo:
        session["token"] = token_demo
        session["tipo_conta"] = "demo"
        return jsonify({"status": "ok"})
    return jsonify({"status": "erro", "mensagem": "Token demo não cadastrado."})


# Adicionar rota para debug
@app.route("/debug_licencas")
def debug_licencas():
    if request.remote_addr == "127.0.0.1":
        licencas = carregar_licencas()
        return jsonify(licencas)
    return "Acesso negado", 403


# ---------------- CONECTAR REAL -----------------


@app.route("/conectar_real", methods=["POST"])
def conectar_real():
    token_real = session.get("token_deriv_real")
    if token_real:
        session["token"] = token_real
        session["tipo_conta"] = "real"
        return jsonify({"status": "ok"})
    return jsonify({"status": "erro", "mensagem": "Token real não cadastrado."})


# ----------------------- Login automático -----------------------


@app.before_request
def login_automatico():
    """Se a sessão estiver vazia, tenta autenticar por IP ou HWID automaticamente."""
    # Ignora rotas de recursos estáticos
    if request.endpoint and request.endpoint.startswith("static"):
        return

    if "email" not in session:
        ip = request.remote_addr
        hwid = get_hwid()
        licenca = buscar_licenca_por_ip_ou_hwid(ip, hwid)
        if licenca:
            # Salva ID da licença para uso posterior nas rotas de troca de conta
            for key, value in carregar_licencas().items():
                if value == licenca:
                    session["licenca_id"] = key
                    break

            # Salva código da licença na sessão
            if licenca.get("codigo_licenca"):
                session["codigo_licenca"] = licenca.get("codigo_licenca")

            # Verifica status da licença
            status = licenca.get("status", "ativa")

            # Se a licença estiver no status 'gerada', redireciona para ativação
            if status == "gerada":
                session["erro_licenca"] = (
                    "Sua licença foi gerada, mas precisa ser ativada. Por favor, informe seus tokens da Deriv para ativar."
                )
                return redirect(url_for("ativacao"))

            if status != "ativa":
                # Redireciona para página de licença expirada/revogada
                session["erro_licenca"] = (
                    f"Sua licença está {status}. Entre em contato com o suporte."
                )
                return redirect(url_for("login"))

            # Salva informações da licença na sessão
            session["email"] = licenca["email"]
            session["plano"] = licenca.get("plano", "free")
            session["validade"] = licenca.get("validade", "N/A")

            # Seleciona token real se MODO_REAL verdadeiro, senão demo
            token_real = licenca.get("token_deriv_real")
            token_demo = licenca.get("token_deriv_demo")
            session["token"] = (
                token_real
                if licenca.get("tipo_conta") == "real"
                else token_demo or token_real
            )
            session["tipo_conta"] = licenca.get("tipo_conta", "demo")
            session["token_deriv_demo"] = token_demo
            session["token_deriv_real"] = token_real
            session["deriv_account"] = licenca.get("deriv_real") or licenca.get(
                "deriv_demo"
            )

            # Se a rota solicitada era /login, redireciona direto para painel
            if request.endpoint == "login":
                return redirect(url_for("painel"))


if __name__ == "__main__":
    # Inicializa o módulo de administração
    admin.init_app(app)

    app.run(host="0.0.0.0", port=5000, debug=True)
