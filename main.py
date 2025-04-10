import os
import json
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "segredo_super_top_do_lucas")
LICENCAS_PATH = "licencas.json"

# === UTILITÁRIOS ===
def get_ip():
    return request.remote_addr

def get_hwid():
    return str(hex(uuid.getnode()))

# === HOME ===
@app.route("/")
def home():
    if "token_deriv" in session:
        return redirect("/painel")
    return redirect("/login")

# === LOGIN COM CHAVE ===
@app.route("/login")
def login():
    chave = request.args.get("chave")
    if chave and os.path.exists(LICENCAS_PATH):
        with open(LICENCAS_PATH, "r") as f:
            licencas = json.load(f)
        if chave in licencas:
            session["chave_ativacao"] = chave
            session["ativado_auto"] = True
    return render_template("login.html")

# === REDIRECIONAMENTO PARA O LOGIN COM CHAVE NA URL ===
@app.route("/ativar")
def ativar():
    chave = request.args.get("chave")
    return redirect(f"/login?chave={chave}")

# === VALIDAÇÃO AUTOMÁTICA DO TOKEN ===
@app.route("/validar_token")
def validar_token():
    token = request.args.get("token1")
    conta = request.args.get("acct1")
    ip = get_ip()
    hwid = get_hwid()

    if not token or not conta:
        return "Token ou conta não informados.", 400

    chave = session.get("chave_ativacao")
    if not chave or not os.path.exists(LICENCAS_PATH):
        return render_template("acesso_negado.html"), 403

    with open(LICENCAS_PATH, "r") as f:
        licencas = json.load(f)

    licenca = licencas.get(chave)
    if not licenca:
        return render_template("acesso_negado.html"), 403

    # Garante estrutura mínima
    licenca.setdefault("ips", [])
    licenca.setdefault("hwids", [])
    licenca.setdefault("token", "")
    licenca.setdefault("deriv_account", "")
    licenca.setdefault("ativado_em", "")
    licenca.setdefault("usada", False)

    if not licenca["usada"]:
        # Primeira vez: salva tudo
        licenca["ips"].append(ip)
        licenca["hwids"].append(hwid)
        licenca["token"] = token
        licenca["deriv_account"] = conta
        licenca["ativado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        licenca["usada"] = True
    else:
        # Validação 2 de 3 (token + ip + hwid)
        token_ok = token == licenca["token"]
        ip_ok = ip in licenca["ips"]
        hwid_ok = hwid in licenca["hwids"]
        validacoes = sum([token_ok, ip_ok, hwid_ok])

        if validacoes < 2:
            return render_template("acesso_negado.html"), 403

        # Atualiza IP ou HWID se novo
        if not ip_ok:
            licenca["ips"].append(ip)
        if not hwid_ok:
            licenca["hwids"].append(hwid)

    # Salva licenças atualizadas
    with open(LICENCAS_PATH, "w") as f:
        json.dump(licencas, f, indent=2)

    # Seta sessão
    session.permanent = True
    session["token_deriv"] = token
    session["email"] = conta

    return redirect("/configuracao")

# === CONFIGURAÇÃO INICIAL (escolher modo e aceitar termos) ===
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

# === PAINEL FINAL ===
@app.route("/painel")
def painel():
    if "token_deriv" not in session or "tipo_conta" not in session:
        return redirect("/")

    chave = session.get("chave_ativacao")
    if not chave or not os.path.exists(LICENCAS_PATH):
        return redirect("/")

    with open(LICENCAS_PATH, "r") as f:
        licencas = json.load(f)

    licenca = licencas.get(chave)
    if not licenca or not licenca.get("usada", False):
        return render_template("acesso_negado.html"), 403

    return render_template("painel.html")

# === LOGOUT ===
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# === EXECUTAR LOCAL ===
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
