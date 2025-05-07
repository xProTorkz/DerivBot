#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Admin - DerivBot
---------------
Este módulo implementa o painel de administração para gerenciar licenças do DerivBot.
Ele contém rotas para autenticação, criação, listagem e gerenciamento de licenças.
"""

import os
import json
from flask import (
    Blueprint,
    render_template,
    request,
    session,
    redirect,
    url_for,
    jsonify,
)
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from datetime import datetime
import gerador_licencas

# Configuração
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Dados de acesso do administrador (deve ser movido para um arquivo .env ou banco de dados)
ADMIN_USERS = {
    "admin@derivbot.com": {
        "senha_hash": generate_password_hash("admin123"),
        "nome": "Administrador",
    }
}


# Decorador para proteção de rotas
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_email" not in session:
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)

    return decorated_function


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    erro = None
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")

        if email in ADMIN_USERS and check_password_hash(
            ADMIN_USERS[email]["senha_hash"], senha
        ):
            session["admin_email"] = email
            session["admin_nome"] = ADMIN_USERS[email]["nome"]
            return redirect(url_for("admin.licencas"))
        else:
            erro = "Email ou senha inválidos. Tente novamente."

    return render_template("admin_login.html", erro=erro)


@admin_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("admin_email", None)
    session.pop("admin_nome", None)
    return jsonify({"status": "ok"})


@admin_bp.route("/licencas")
@admin_required
def licencas():
    # Obtém todas as licenças
    licencas = gerador_licencas.carregar_licencas()

    # Verifica se há mensagem de feedback
    mensagem = session.pop("mensagem", None)
    tipo_mensagem = session.pop("tipo_mensagem", "success")

    # Contagem de licenças por status
    stats = {
        "total": len(licencas),
        "ativas": sum(1 for lic in licencas.values() if lic.get("status") == "ativa"),
        "geradas": sum(1 for lic in licencas.values() if lic.get("status") == "gerada"),
        "expiradas": sum(
            1 for lic in licencas.values() if lic.get("status") == "expirada"
        ),
        "revogadas": sum(
            1 for lic in licencas.values() if lic.get("status") == "revogada"
        ),
    }

    return render_template(
        "admin_licencas.html",
        licencas=licencas,
        mensagem=mensagem,
        tipo_mensagem=tipo_mensagem,
        stats=stats,
    )


@admin_bp.route("/licencas/criar", methods=["POST"])
@admin_required
def criar_licenca():
    email = request.form.get("email")
    nome = request.form.get("nome")
    plano = request.form.get("plano")

    if not email or not plano:
        session["mensagem"] = "Email e plano são obrigatórios."
        session["tipo_mensagem"] = "danger"
        return redirect(url_for("admin.licencas"))

    resultado = gerador_licencas.criar_licenca(email, plano, nome)

    if "erro" in resultado:
        session["mensagem"] = resultado["erro"]
        session["tipo_mensagem"] = "danger"
    else:
        codigo = resultado["codigo_licenca"]
        session["mensagem"] = f"Licença criada com sucesso! Código: {codigo}"
        session["tipo_mensagem"] = "success"

    return redirect(url_for("admin.licencas"))


@admin_bp.route("/licencas/revogar/<codigo>", methods=["POST"])
@admin_required
def revogar_licenca(codigo):
    resultado = gerador_licencas.revogar_licenca(codigo)
    return jsonify(resultado)


@admin_bp.route("/licencas/atualizar", methods=["POST"])
@admin_required
def atualizar_licenca():
    dados = request.json
    codigo = dados.get("codigo")
    plano = dados.get("plano")

    if not codigo or not plano:
        return jsonify({"erro": "Código da licença e plano são obrigatórios."})

    resultado = gerador_licencas.atualizar_licenca(codigo, plano)
    return jsonify(resultado)


@admin_bp.route("/licencas/verificar", methods=["POST"])
@admin_required
def verificar_licencas():
    resultado = gerador_licencas.verificar_licencas_expiradas()
    return jsonify(resultado)


def init_app(app):
    """Inicializa o Blueprint na aplicação Flask"""
    app.register_blueprint(admin_bp)

    # Registra um usuário administrador padrão se não existir
    if not os.path.exists(".env") or "ADMIN_EMAIL" not in os.environ:
        print(
            "[AVISO] Configuração do administrador não encontrada. Usando valores padrão!"
        )
