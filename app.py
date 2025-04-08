import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.makedirs("tokens", exist_ok=True)


# from flask_dance.contrib.google import make_google_blueprint, google
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
APP_ID = '71203'  # Seu App ID da Deriv
REDIRECT_URI = 'https://a7bd-200-152-5-73.ngrok-free.app/oauth'


app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = 'segredo_super_secreto'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)
app.config['SESSION_PERMANENT'] = False
os.makedirs("tokens", exist_ok=True)

# google_bp = make_google_blueprint(
#     client_id="178869871460-eg7bpjqmour6sinmbdff33dk1kieut0h.apps.googleusercontent.com",
#     client_secret="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",
#     redirect_url="/login/google/authorized",
#     scope=["openid", "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email"]
# )
# app.register_blueprint(google_bp, url_prefix="/login")



# =============== STATUS DO ROBÔ (VISUALIZAÇÃO DO PAINEL) ===============
status_robo = {
    "saldo": 0.0,
    "status": "Parado",
    "logs": []
}

# =============== ROTA PRINCIPAL ===============
@app.route('/')
def index():
    # Se estiver logado e com token válido, vai direto pro painel
    if session.get('logado') and session.get('token'):
        return redirect(url_for('painel'))

    # Se estiver logado, mas ainda não completou o login OAuth (sem token)
    elif session.get('logado'):
        return redirect(url_for('token'))

    # Se não estiver logado, mostra a tela de login
    return render_template('login.html')




# =============== LOGIN SIMPLES ===============
@app.route('/login', methods=['POST'])
def login():
    senha = request.form.get('senha')
    if senha == "123":
        session['logado'] = True
        session['token'] = None  # Garante que ainda não tem token
        return redirect(url_for('token'))  # Vai direto pra página de token
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

        token = session.get('token')

        if not token:
            status_robo["logs"].append("❌ Token não encontrado na sessão.")
            return "Token não encontrado na sessão"

        status_robo["logs"].append("🔐 Token da sessão carregado com sucesso.")

        def executar():
            bot_deriv.MODO_ATUAL = modo
            bot_deriv.status_robo = status_robo
            bot_deriv.TOKEN = token
            bot_deriv.iniciar_websocket()

            # 👇 inicia o loop de operação IA
            threading.Thread(target=bot_deriv.loop_operacional).start()
        return f"Robô iniciado no modo {modo.upper()}"

    return "Modo não selecionado."



# =============== STATUS EM TEMPO REAL (PARA JAVASCRIPT) ===============
@app.route('/status_robo')
def status_robo_route():
    return jsonify(status_robo)

# Exibe tela de inserção do token
@app.route('/token')
def token():
    if 'logado' in session:
        if 'token' in session and session['token']:
            return redirect(url_for('painel'))  # Já tem token, vai pro painel
        return render_template('inserir_token.html')  # Mostra campo para inserir token
    return redirect(url_for('index'))





# =============== TOKEN ===============
@app.route('/inserir_token', methods=['GET', 'POST'])
def inserir_token():
    if request.method == 'POST':
        token = request.form['token']
        
        # Simplesmente salva o token na sessão e vai pro painel
        session['token'] = token
        session['login_id'] = "ID_DERIV"  # Coloca algo temporário
        return redirect('/painel')

    return render_template('inserir_token.html')



# Salva o token criptografado
@app.route('/salvar_token', methods=['POST'])
def salvar_token():
    print("🔐 Rota /salvar_token acessada")
    return "Salvamento de token desativado temporariamente."

# =============== PAINEL ===============
@app.route('/painel')
def painel():
    token = session.get('token')
    
    # Se não estiver logado ou não tiver token, redireciona
    if not session.get('logado') or not token:
        return redirect(url_for('token'))

    # Tudo certo, renderiza o painel com o login_id (se tiver)
    return render_template('painel.html', login_id=session.get('login_id'))



@app.route('/oauth')
def oauth_callback():
    token = request.args.get('token')
    if token:
        session['token'] = token
        return f'''
            <h3>Login realizado com sucesso!</h3>
            <p><strong>Token:</strong> {token}</p>
            <a href="/painel">Ir para o Painel</a>
        '''
    else:
        return 'Erro ao obter token da Deriv.'

# =============== LOGIN GOOGLE ===============
# @app.route('/login/google/authorized')
# def google_login_callback():
#     resp = google.get("/oauth2/v2/userinfo")
#     if not resp.ok:
#         return redirect(url_for('index'))

#     user_info = resp.json()

#     session['logado'] = True
#     session['google_id'] = user_info.get("id")
#     session['nome'] = user_info.get("name")
#     session['email'] = user_info.get("email")
#     session['token'] = None
#     session['login_id'] = None

#     return redirect(url_for('token'))


@app.before_request
def mostrar_sessao():
    print("Sessão atual:", dict(session))



# =============== EXECUÇÃO ===============
if __name__ == '__main__':
    app.run(debug=True)