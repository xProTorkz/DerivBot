import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask_dance.contrib.google import make_google_blueprint, google
from flask_session import Session
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import threading
import bot_deriv  # O bot deve estar no mesmo diretório ou ser importável
from cryptography.fernet import Fernet
import json

# Garante que a chave de criptografia seja fixa
if os.path.exists("chave.key"):
    with open("chave.key", "rb") as f:
        CHAVE_CRIPTO = f.read()
else:
    CHAVE_CRIPTO = Fernet.generate_key()
    with open("chave.key", "wb") as f:
        f.write(CHAVE_CRIPTO)

fernet = Fernet(CHAVE_CRIPTO)


app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = 'segredo_super_secreto'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
app.config['SESSION_PERMANENT'] = False

google_bp = make_google_blueprint(
    client_id="178869871460-eg7bpjqmour6sinmbdff33dk1kieut0h.apps.googleusercontent.com",
    client_secret="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",
    redirect_url="/login/google/authorized",
    scope=["openid", "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email"]

)

app.register_blueprint(google_bp, url_prefix="/login")


# =============== STATUS DO ROBÔ (VISUALIZAÇÃO DO PAINEL) ===============
status_robo = {
    "saldo": 0.0,
    "status": "Parado",
    "logs": []
}

# =============== ROTA PRINCIPAL ===============
@app.route('/')
def index():
    if 'logado' in session and 'google_id' in session:
        return render_template('painel.html')
    return render_template('login.html')


# =============== LOGIN SIMPLES ===============
@app.route('/login', methods=['POST'])
def login():
    senha = request.form.get('senha')
    print("Tentativa de login:", senha)  # DEBUG!
    if senha == "123":
        session['logado'] = True
        return redirect(url_for('index'))
    return "Senha incorreta!"

# =============== LOGOUT ===============
@app.route('/logout')
def logout():
    session.pop('logado', None)
    return redirect(url_for('index'))

# =============== INICIAR ROBÔ ===============
@app.route('/iniciar_robo', methods=['POST'])
def iniciar_robo():
    modo = request.form.get('modo')
    if modo:
        status_robo["status"] = f"Iniciando modo: {modo}"
        status_robo["logs"].append(f"🚀 Iniciando modo: {modo.upper()}")

        token = None

        try:
            if 'google_id' in session:
                with open(f"tokens/{session['google_id']}.json", 'r') as f:
                    token_cripto = json.load(f)["token_cripto"]
                    token = fernet.decrypt(token_cripto.encode()).decode()
                    status_robo["logs"].append("🔐 Token da conta Google carregado com sucesso.")
            else:
                with open("tokens/token_manual.json", "r") as f:
                    token_cripto = json.load(f)["token_cripto"]
                    token = fernet.decrypt(token_cripto.encode()).decode()
                    status_robo["logs"].append("🔐 Token manual carregado com sucesso.")
        except Exception as e:
            status_robo["logs"].append(f"❌ Erro ao carregar token: {str(e)}")
            return "Erro ao carregar token"

        def executar():
            bot_deriv.MODO_ATUAL = modo
            bot_deriv.status_robo = status_robo
            bot_deriv.TOKEN = token
            bot_deriv.iniciar_websocket()

        threading.Thread(target=executar).start()
        return f"Robô iniciado no modo {modo.upper()}"
    return "Modo não selecionado."


# =============== STATUS EM TEMPO REAL (PARA JAVASCRIPT) ===============
@app.route('/status_robo')
def status_robo_route():
    return jsonify(status_robo)

# Exibe tela de inserção do token
@app.route('/token')
def token():
    if 'google_id' in session:
        return render_template('inserir_token.html')
    return redirect(url_for('index'))

# =============== TOKEN ===============
# Salva o token criptografado
@app.route('/salvar_token', methods=['POST'])
def salvar_token():
    token = request.form.get('token')
    if not token:
        return "Token vazio!"

    token_cripto = fernet.encrypt(token.encode()).decode()
    if 'google_id' in session:
        filename = f"tokens/{session['google_id']}.json"
    else:
        filename = "tokens/token_manual.json"

    dados = {
        "token_cripto": token_cripto
    }
    with open(filename, 'w') as f:
        json.dump(dados, f)
    return redirect(url_for('index'))
# =============== LOGIN GOOGLE ===============
@app.route('/login/google/authorized')
def google_login_callback():
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return redirect(url_for('index'))

    user_info = resp.json()
    session['logado'] = True
    session['google_id'] = user_info["id"]

    # Verifica se já tem token salvo
    try:
        with open(f"tokens/{session['google_id']}.json", 'r') as f:
            return redirect(url_for('index'))
    except FileNotFoundError:
        return redirect(url_for('token'))



# =============== EXECUÇÃO ===============
if __name__ == '__main__':
    app.run(debug=True)