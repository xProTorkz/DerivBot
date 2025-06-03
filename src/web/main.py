import os
import json
from datetime import datetime
from typing import Dict, Any
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from functools import wraps

from ..core.app import app as bot_app
from ..core.config import config
from ..utils.gerador_licencas import licenca_manager

# Configuração do Flask
flask_app = Flask(__name__)
flask_app.secret_key = os.urandom(24)
flask_app.config["SESSION_TYPE"] = "filesystem"
flask_app.config["PERMANENT_SESSION_LIFETIME"] = config.SECURITY["session_timeout"]

# Configuração do Login
login_manager = LoginManager()
login_manager.init_app(flask_app)
login_manager.login_view = "login"


class User(UserMixin):
    def __init__(self, email):
        self.id = email


@login_manager.user_loader
def load_user(email):
    if licenca_manager.validar_licenca(email, session.get("token", "")):
        return User(email)
    return None


# Decorator para verificar admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not licenca_manager.is_admin(
            current_user.id
        ):
            return jsonify({"error": "Acesso negado"}), 403
        return f(*args, **kwargs)

    return decorated_function


# Rotas
@flask_app.route("/")
def index():
    return render_template("index.html")


@flask_app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        token = request.form.get("token")

        if licenca_manager.validar_login(email, token):
            user = User(email)
            login_user(user)
            session["token"] = token
            return redirect(url_for("painel"))

        return render_template("login.html", error="Credenciais inválidas")

    return render_template("login.html")


@flask_app.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("token", None)
    return redirect(url_for("index"))


@flask_app.route("/painel")
@login_required
def painel():
    return render_template("painel.html")


@flask_app.route("/admin")
@login_required
@admin_required
def admin():
    return render_template("admin.html")


# API Routes
@flask_app.route("/api/bot/start", methods=["POST"])
@login_required
def start_bot():
    try:
        if bot_app.iniciar():
            return jsonify({"status": "success"})
        return jsonify({"error": "Falha ao iniciar bot"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@flask_app.route("/api/bot/stop", methods=["POST"])
@login_required
def stop_bot():
    try:
        bot_app.parar()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@flask_app.route("/api/bot/status")
@login_required
def bot_status():
    try:
        return jsonify(bot_app.get_status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@flask_app.route("/api/bot/historico")
@login_required
def bot_historico():
    try:
        inicio = request.args.get("inicio")
        fim = request.args.get("fim")
        limite = int(request.args.get("limite", 100))

        if inicio:
            inicio = datetime.fromisoformat(inicio)
        if fim:
            fim = datetime.fromisoformat(fim)

        operacoes = bot_app.catalogador.get_operacoes(
            inicio=inicio, fim=fim, limite=limite
        )

        return jsonify(operacoes)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@flask_app.route("/api/bot/analise")
@login_required
def bot_analise():
    try:
        return jsonify(bot_app.inteligencia.get_ultima_analise())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@flask_app.route("/api/admin/users", methods=["GET", "POST"])
@login_required
@admin_required
def admin_users():
    if request.method == "POST":
        try:
            email = request.json.get("email")
            duracao = request.json.get("duracao", 30)
            admin = request.json.get("admin", False)

            licenca = licenca_manager.gerar_licenca(
                email=email, duracao_dias=duracao, admin=admin
            )

            if licenca:
                return jsonify({"status": "success"})
            return jsonify({"error": "Falha ao gerar licença"}), 500

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    try:
        licencas = licenca_manager.listar_licencas()
        return jsonify(licencas)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@flask_app.route("/api/admin/users/<email>", methods=["DELETE"])
@login_required
@admin_required
def admin_revoke_user(email):
    try:
        if licenca_manager.revocar_licenca(email):
            return jsonify({"status": "success"})
        return jsonify({"error": "Falha ao revogar licença"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@flask_app.route("/api/contact", methods=["POST"])
def contact():
    try:
        nome = request.json.get("nome")
        email = request.json.get("email")
        mensagem = request.json.get("mensagem")

        # TODO: Implementar envio de email

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=5000, debug=config.DEBUG)
