#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Arquivo principal do DerivBot - Versão Enxuta
Responsável por inicializar o servidor Flask e gerenciar as rotas principais
"""

import os
import json
import logging
import secrets

from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv

# Importações locais
from utils.motor import DerivAPI
from src.core.motor import Motor
from utils.endpoints_estado import EstadoAPI
from src.utils.gerador_licencas import (
    carregar_licencas,
    salvar_licencas,
    validar_dispositivo,
    vincular_dispositivo,
    obter_hwid,
    obter_ip,
)

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("derivbot.log"), logging.StreamHandler()],
)
logger = logging.getLogger("DerivBot")

# Diretório para armazenamento de dados
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Arquivo para armazenamento de licenças
LICENCAS_FILE = os.path.join(DATA_DIR, "licencas.json")

# Garante que o arquivo de licenças existe
if not os.path.exists(LICENCAS_FILE):
    try:
        with open(LICENCAS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2, ensure_ascii=False)
        logger.info("Arquivo de licenças criado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao criar arquivo de licenças: {e}")

# Inicialização do Flask
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(16))
app.config["SESSION_TYPE"] = "filesystem"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config["SESSION_FILE_DIR"] = os.path.join(DATA_DIR, "flask_session")
app.config["SESSION_PERMANENT"] = True

# Garante que o diretório de sessão existe
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)

# Inicialização das APIs
estado_api = EstadoAPI()
deriv_api = None
motor = None

# Variáveis globais
robo_ativo = False
modo_operacao = "iniciante"
meta_diaria = 100.0  # Meta padrão alterada para 100
historico_operacoes = []
lucro_atual = 0.0
saldo_atual = 0.0
ultima_mensagem = "Robô pronto para iniciar."
contador_operacoes = 0
status_operacao = "parado"

# Sistema de autenticação baseado apenas em licencas.json
# Não criamos mais tokens.json - tudo é gerenciado via licenças


def verificar_token(token):
    """Verifica se o token é válido"""
    if not token:
        return False, "Token não fornecido"

    try:
        # Carrega as licenças para obter dados corretos da conta
        licencas = carregar_licencas()
        conta_id = None
        tipo_conta = None
        saldo = None

        # Procura o token nas licenças para obter dados corretos
        for licenca in licencas.values():
            if licenca.get("token_deriv_real") == token:
                conta_id = licenca.get("deriv_real")
                tipo_conta = "real"
                # Tenta obter saldo real da API
                api_temp = DerivAPI(token)
                if api_temp.conectado:
                    resultado_saldo = api_temp.obter_saldo()
                    if resultado_saldo.get("status") == "ok":
                        saldo = resultado_saldo["saldo"]
                    else:
                        saldo = 0.0  # Saldo padrão se não conseguir obter
                else:
                    saldo = 0.0
                break
            elif licenca.get("token_deriv_demo") == token:
                conta_id = licenca.get("deriv_demo")
                tipo_conta = "demo"
                # Tenta obter saldo real da API
                api_temp = DerivAPI(token)
                if api_temp.conectado:
                    resultado_saldo = api_temp.obter_saldo()
                    if resultado_saldo.get("status") == "ok":
                        saldo = resultado_saldo["saldo"]
                    else:
                        saldo = 10000.0  # Saldo padrão demo se não conseguir obter
                else:
                    saldo = 10000.0
                break

        # Se não encontrou nas licenças, usa verificação padrão
        if not conta_id:
            api_temp = DerivAPI(token)
            resultado = api_temp.verificar_token()
            if resultado.get("status") == "ok":
                return True, resultado
            else:
                return False, resultado.get("mensagem", "Token inválido")

        # Retorna dados da licença
        return True, {
            "status": "ok",
            "conta_id": conta_id,
            "conta_nome": "Usuário",
            "conta_tipo": tipo_conta,
            "saldo": saldo,
        }

    except Exception as e:
        logger.error(f"Erro ao verificar token: {e}")
        return False, str(e)


def inicializar_api(token):
    """Inicializa a API e o Motor com o token fornecido"""
    global deriv_api, motor
    try:
        # Inicializa a API simples
        deriv_api = DerivAPI(token)

        # Inicializa o motor (mesmo se der erro, continua)
        try:
            motor = Motor()
            motor.conectar(token)
            logger.info("Motor inicializado com sucesso")
        except Exception as motor_error:
            logger.warning(f"Erro ao inicializar motor: {motor_error}")
            # Cria motor básico mesmo com erro
            motor = Motor()
            motor.token = token
            motor.conectado = True  # Marca como conectado em modo básico
            motor.rodando = False  # Inicialmente parado
            logger.info("Motor criado em modo básico")

        return True
    except Exception as e:
        logger.error(f"Erro ao inicializar API: {e}")
        return False


def verificar_autenticacao_automatica():
    """Verifica se o usuário pode fazer login automático baseado em HWID, IP e licença ativa"""
    try:
        hwid_atual = obter_hwid()
        ip_atual = obter_ip()

        logger.info(
            f"Verificando autenticação automática - HWID: {hwid_atual}, IP: {ip_atual}"
        )

        licencas = carregar_licencas()

        for _, licenca in licencas.items():
            # Verifica se a licença está ativa
            if licenca.get("status") != "ativa":
                continue

            # Verifica se a licença não expirou
            validade = licenca.get("validade")
            if validade != "VITALÍCIO":
                try:
                    data_validade = datetime.strptime(validade, "%Y-%m-%d")
                    if datetime.now() > data_validade:
                        continue
                except:
                    continue

            # Conta quantos fatores conferem
            fatores_conferidos = 0

            # Fator 1: HWID
            if hwid_atual and hwid_atual in licenca.get("hwids", []):
                fatores_conferidos += 1
                logger.info("HWID confere")

            # Fator 2: IP
            if ip_atual and ip_atual in licenca.get("ips", []):
                fatores_conferidos += 1
                logger.info("IP confere")

            # Fator 3: Licença ativa (sempre confere se chegou até aqui)
            fatores_conferidos += 1
            logger.info("Licença ativa confere")

            # Se pelo menos 2 dos 3 fatores conferem, permite login automático
            if fatores_conferidos >= 2:
                logger.info(
                    f"Autenticação automática aprovada para licença {licenca.get('codigo_licenca')}"
                )
                return licenca

        logger.info("Nenhuma licença válida encontrada para autenticação automática")
        return None

    except Exception as e:
        logger.error(f"Erro na verificação de autenticação automática: {e}")
        return None


def obter_tokens_da_licenca(licenca):
    """Obtém os tokens da licença"""
    token_real = licenca.get("token_deriv_real")
    token_demo = licenca.get("token_deriv_demo")
    return token_real, token_demo


def salvar_historico():
    """Salva o histórico de operações"""
    try:
        with open(os.path.join(DATA_DIR, "historico.json"), "w", encoding="utf-8") as f:
            json.dump(historico_operacoes, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Erro ao salvar histórico: {e}")


def carregar_historico():
    """Carrega o histórico de operações"""
    global historico_operacoes
    try:
        if os.path.exists(os.path.join(DATA_DIR, "historico.json")):
            with open(
                os.path.join(DATA_DIR, "historico.json"), "r", encoding="utf-8"
            ) as f:
                historico_operacoes = json.load(f)
    except Exception as e:
        logger.error(f"Erro ao carregar histórico: {e}")
        historico_operacoes = []


def adicionar_operacao(tipo, valor, resultado):
    """Adiciona uma operação ao histórico"""
    global historico_operacoes, contador_operacoes

    agora = datetime.now()
    operacao = {
        "data": agora.strftime("%d/%m/%Y"),
        "hora": agora.strftime("%H:%M:%S"),
        "timestamp": agora.timestamp(),
        "tipo": tipo,
        "valor": valor,
        "resultado_real": resultado,
    }

    historico_operacoes.append(operacao)
    contador_operacoes += 1
    salvar_historico()


# Rotas do Flask
@app.route("/")
def index():
    """Rota principal - Login"""
    # Verifica se já está logado
    if "token" in session:
        return redirect(url_for("painel"))

    # Tenta autenticação automática
    licenca_auto = verificar_autenticacao_automatica()
    if licenca_auto:
        logger.info("Realizando login automático...")

        # Obtém os tokens da licença
        token_real, token_demo = obter_tokens_da_licenca(licenca_auto)

        # Prioriza token real se disponível
        if token_real:
            token_principal = token_real
            tipo_conta_preferido = "real"
        elif token_demo:
            token_principal = token_demo
            tipo_conta_preferido = "demo"
        else:
            token_principal = None

        if token_principal:
            # Verifica se o token ainda é válido
            valido, resultado = verificar_token(token_principal)

            if valido:
                # Configura a sessão automaticamente
                session.permanent = True
                session["codigo_licenca"] = licenca_auto.get("codigo_licenca")
                session["token"] = token_principal

                # Usa o tipo de conta baseado no token escolhido
                session["tipo_conta"] = tipo_conta_preferido

                # Salva os tokens na sessão
                if token_real:
                    session["token_real"] = token_real
                if token_demo:
                    session["token_demo"] = token_demo

                # Usa o ID da conta da licença se disponível
                if tipo_conta_preferido == "real" and licenca_auto.get("deriv_real"):
                    session["deriv_account"] = licenca_auto["deriv_real"]
                elif tipo_conta_preferido == "demo" and licenca_auto.get("deriv_demo"):
                    session["deriv_account"] = licenca_auto["deriv_demo"]
                else:
                    session["deriv_account"] = resultado.get("conta_id", "")

                session["saldo"] = resultado.get("saldo", 0)

                # Inicializa a API
                inicializar_api(token_principal)

                logger.info("Login automático realizado com sucesso")
                return redirect(url_for("painel"))
            else:
                logger.warning(
                    "Token da licença inválido, redirecionando para login manual"
                )
        else:
            logger.warning(
                "Nenhum token encontrado na licença, redirecionando para login manual"
            )

    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    """Rota de login"""
    token_real = request.form.get("token_deriv_real")
    token_demo = request.form.get("token_deriv_demo")
    codigo_licenca = request.form.get("codigo_licenca")

    logger.info(f"Tentativa de login - Código: {codigo_licenca}")

    # Verifica se pelo menos um token foi fornecido
    if not token_real and not token_demo:
        return render_template(
            "login.html", erro="Pelo menos um token deve ser fornecido"
        )

    # Determina qual token usar e o tipo de conta
    if token_real:
        token_principal = token_real
        tipo_conta_escolhido = "real"
    else:
        token_principal = token_demo
        tipo_conta_escolhido = "demo"

    # Verifica se o token é válido
    valido, resultado = verificar_token(token_principal)

    if valido:
        # Carrega a licença
        licencas = carregar_licencas()
        licenca = None

        # Procura a licença pelo código
        for l in licencas.values():
            if l.get("codigo_licenca") == codigo_licenca:
                licenca = l
                logger.info(
                    f"Licença encontrada: {json.dumps(licenca, indent=2, ensure_ascii=False)}"
                )
                break

        if not licenca:
            logger.warning(f"Licença não encontrada para o código: {codigo_licenca}")
            return render_template("login.html", erro="Licença não encontrada")

        # Se é primeiro acesso, vincula o dispositivo
        if not licenca.get("hwids") and not licenca.get("ips"):
            logger.info("Primeiro acesso - Vinculando dispositivo")
            licenca = vincular_dispositivo(licenca)

            # Salva os tokens na licença se fornecidos
            if token_real:
                licenca["token_deriv_real"] = token_real
            if token_demo:
                licenca["token_deriv_demo"] = token_demo

            # Atualiza o arquivo de licenças
            for key, lic in licencas.items():
                if lic.get("codigo_licenca") == codigo_licenca:
                    licencas[key] = licenca
                    break
            salvar_licencas(licencas)
        else:
            # Verifica se o dispositivo está autorizado
            if not validar_dispositivo(licenca):
                logger.warning("Dispositivo não autorizado")
                return render_template(
                    "login.html", erro="Dispositivo não autorizado. Compre uma licença."
                )

        # Marca a sessão como permanente
        session.permanent = True

        # Salva o código da licença na sessão
        session["codigo_licenca"] = codigo_licenca

        # Salva o token principal na sessão
        session["token"] = token_principal

        # Usa o tipo de conta baseado no token fornecido
        session["tipo_conta"] = tipo_conta_escolhido

        # Salva os tokens na sessão e arquivo
        if token_real:
            session["token_real"] = token_real
        if token_demo:
            session["token_demo"] = token_demo

        # Verifica se há tokens salvos na licença
        if licenca.get("token_deriv_real") and not token_real:
            session["token_real"] = licenca["token_deriv_real"]
        if licenca.get("token_deriv_demo") and not token_demo:
            session["token_demo"] = licenca["token_deriv_demo"]

        # Usa o ID da conta da licença se disponível
        if tipo_conta_escolhido == "real" and licenca.get("deriv_real"):
            session["deriv_account"] = licenca["deriv_real"]
        elif tipo_conta_escolhido == "demo" and licenca.get("deriv_demo"):
            session["deriv_account"] = licenca["deriv_demo"]
        else:
            session["deriv_account"] = resultado.get("conta_id", "")

        session["saldo"] = resultado.get("saldo", 0)

        # Inicializa a API com o token principal
        inicializar_api(token_principal)

        # Redireciona para o painel
        return redirect(url_for("painel"))
    else:
        # Exibe mensagem de erro
        return render_template("login.html", erro=f"Token inválido: {resultado}")


@app.route("/painel")
def painel():
    """Rota do painel"""
    if "token" not in session:
        return redirect(url_for("index"))

    # Carrega o histórico
    carregar_historico()

    # Carrega a licença
    licencas = carregar_licencas()
    licenca = None
    codigo_licenca = session.get("codigo_licenca")

    # Procura a licença pelo código
    if codigo_licenca:
        for l in licencas.values():
            if l.get("codigo_licenca") == codigo_licenca:
                licenca = l
                break

    # Prepara dados para o template
    tipo_conta = session.get("tipo_conta", "demo")
    saldo = session.get("saldo", 0)

    # Informações da licença
    if licenca:
        codigo_licenca = licenca.get("codigo_licenca")
        plano = licenca.get("plano", "free")
        validade = licenca.get("validade", "N/A")
    else:
        codigo_licenca = "N/A"
        plano = "free"
        validade = "N/A"

    return render_template(
        "painel.html",
        tipo_conta=tipo_conta,
        saldo=saldo,
        codigo_licenca=codigo_licenca,
        plano=plano,
        validade=validade,
        historico=historico_operacoes[-10:] if historico_operacoes else [],
    )


@app.route("/logout")
def logout():
    """Rota para logout"""
    session.clear()
    return redirect(url_for("index"))


@app.route("/toggle_bot", methods=["POST"])
def toggle_bot():
    """Rota para iniciar/parar o robô com sistema inteligente"""
    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        data = request.get_json()
        modo = data.get("modo", "iniciante")

        # Configurações por modo (sincronizado com catalogador.py)
        config_modos = {
            "iniciante": {"meta_padrao": 20.0, "meta_maxima": 20.0},
            "conservador": {"meta_padrao": 50.0, "meta_maxima": 50.0},
            "agressivo": {"meta_padrao": 100.0, "meta_maxima": None},  # Ilimitado
        }

        config_modo = config_modos.get(modo, config_modos["iniciante"])
        meta_solicitada = float(data.get("meta", config_modo["meta_padrao"]))

        # Valida a meta baseada no modo
        meta_maxima = config_modo["meta_maxima"]
        if meta_maxima is not None and meta_solicitada > meta_maxima:
            return (
                jsonify(
                    {
                        "status": "erro",
                        "mensagem": f"Meta excede o limite do modo {modo.upper()} (máximo: ${meta_maxima:.0f})",
                    }
                ),
                400,
            )

        meta = meta_solicitada

        global robo_ativo, modo_operacao, meta_diaria, status_operacao

        if robo_ativo:
            # Verifica proteção antes de parar
            if deriv_api:
                protecao = deriv_api.verificar_protecao_parada()

                if not protecao.get("pode_parar", True):
                    return jsonify(
                        {
                            "status": "aguardando",
                            "mensagem": f"Aguardando operações: {protecao['razao']}",
                            "tempo_espera": protecao.get("tempo_espera", 30),
                        }
                    )

            # Para o robô
            robo_ativo = False
            status_operacao = "parado"

            # Para o motor também
            if motor:
                motor.parar()
            return jsonify(
                {"status": "parado", "mensagem": "Robô parado com segurança"}
            )
        else:
            # Verifica se a API está conectada
            if not deriv_api or not deriv_api.conectado:
                return (
                    jsonify(
                        {
                            "status": "erro",
                            "mensagem": "API não conectada. Verifique sua conexão.",
                        }
                    ),
                    400,
                )

            # Configura o modo no motor diretamente
            if motor is not None:
                motor.modo_operacao = modo
                motor.meta_diaria = meta
                logger.info(f"Modo configurado: {modo} - Meta: ${meta:.2f}")
            else:
                logger.error("Motor não inicializado")

            # Inicia o robô
            robo_ativo = True
            modo_operacao = modo
            meta_diaria = meta
            status_operacao = "analisando"

            # Inicia o sistema inteligente no motor
            if motor is not None:
                motor.iniciar_sistema_inteligente()
                logger.info("Sistema inteligente iniciado no motor")
            else:
                logger.error("Motor não inicializado para iniciar sistema inteligente")

            return jsonify(
                {
                    "status": "iniciado",
                    "modo": modo,
                    "meta": meta,
                    "mensagem": f"Robô iniciado no modo {modo.upper()} com sistema inteligente",
                    "configuracao": {
                        "max_operacoes_simultaneas": {
                            "iniciante": 1,
                            "conservador": 3,
                            "agressivo": 5,
                        }.get(modo, 1),
                        "valor_entrada_percent": "2%",  # Sempre 2% da meta
                        "meta_maxima": {
                            "iniciante": 20,
                            "conservador": 50,
                            "agressivo": None,
                        }.get(modo, 20),
                        "valor_entrada_calculado": f"${meta * 0.02:.2f}",
                    },
                }
            )
    except Exception as e:
        logger.error(f"Erro ao alternar robô: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/status_robo")
def status_robo():
    """Rota para obter status do robô com informações inteligentes"""
    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        # Informações básicas
        status_info = {
            "ativo": robo_ativo,
            "modo": modo_operacao,
            "meta": meta_diaria,
            "lucro": lucro_atual,
            "saldo": saldo_atual,
            "operacoes": contador_operacoes,
            "status_operacao": status_operacao,
            "mensagem_log": ultima_mensagem,
        }

        # Adiciona informações inteligentes se o robô estiver ativo
        if robo_ativo and motor:
            operacoes_ativas = (
                len(motor.operacoes_abertas)
                if hasattr(motor, "operacoes_abertas")
                else 0
            )

            # Configurações do modo atual (sincronizado com catalogador.py)
            config_modo = {
                "iniciante": {"max_ops": 1, "confianca_min": 0.85, "meta_maxima": 20.0},
                "conservador": {
                    "max_ops": 3,
                    "confianca_min": 0.80,
                    "meta_maxima": 50.0,
                },
                "agressivo": {"max_ops": 5, "confianca_min": 0.75, "meta_maxima": None},
            }.get(
                modo_operacao,
                {"max_ops": 1, "confianca_min": 0.85, "meta_maxima": 20.0},
            )

            status_info.update(
                {
                    "sistema_inteligente": {
                        "operacoes_ativas": operacoes_ativas,
                        "max_operacoes_simultaneas": config_modo["max_ops"],
                        "confianca_minima": config_modo["confianca_min"],
                        "valor_entrada_percent": "2%",  # Sempre 2% da meta
                        "progresso_meta": (
                            (lucro_atual / meta_diaria * 100) if meta_diaria > 0 else 0
                        ),
                        "pode_operar": operacoes_ativas < config_modo["max_ops"]
                        and lucro_atual < meta_diaria,
                        "meta_maxima": config_modo["meta_maxima"],
                    },
                    "api_status": {
                        "conectado": motor.conectado if motor else False,
                        "par_atual": (
                            motor.par_atual
                            if motor and hasattr(motor, "par_atual")
                            else "N/A"
                        ),
                        "ultima_cotacao": (
                            motor.ultima_cotacao
                            if motor and hasattr(motor, "ultima_cotacao")
                            else 0
                        ),
                    },
                }
            )

        return jsonify(status_info)
    except Exception as e:
        logger.error(f"Erro ao obter status do robô: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/selecionar_conta", methods=["POST"])
def selecionar_conta():
    """Rota para trocar entre conta demo/real"""
    global saldo_atual, lucro_atual

    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        data = request.get_json()
        tipo = data.get("tipo")

        if tipo not in ["demo", "real"]:
            return (
                jsonify({"status": "erro", "mensagem": "Tipo de conta inválido"}),
                400,
            )

        # Carrega a licença atual para obter os tokens
        licencas = carregar_licencas()
        licenca_atual = None
        codigo_licenca = session.get("codigo_licenca")

        if codigo_licenca:
            for l in licencas.values():
                if l.get("codigo_licenca") == codigo_licenca:
                    licenca_atual = l
                    break

        if not licenca_atual:
            return (
                jsonify({"status": "erro", "mensagem": "Licença não encontrada"}),
                400,
            )

        if tipo == "demo" and licenca_atual.get("token_deriv_demo"):
            # Troca para conta demo
            token = licenca_atual["token_deriv_demo"]
            valido, resultado = verificar_token(token)

            if valido:
                session["token"] = token
                session["tipo_conta"] = "demo"

                # Usa o ID da conta demo da licença se disponível
                if licenca_atual.get("deriv_demo"):
                    session["deriv_account"] = licenca_atual["deriv_demo"]
                else:
                    session["deriv_account"] = resultado.get("conta_id", "")

                # Reinicializa a API
                inicializar_api(token)

                # Aguarda um pouco para a conexão estabelecer
                import time

                time.sleep(1)

                # Obtém saldo real da API
                if deriv_api and deriv_api.conectado and hasattr(deriv_api, "saldo"):
                    saldo_atual = deriv_api.saldo
                else:
                    saldo_atual = resultado.get("saldo", 0)

                session["saldo"] = saldo_atual
                lucro_atual = 0.0  # Reset do lucro ao trocar conta

                return jsonify(
                    {
                        "status": "ok",
                        "mensagem": "Trocado para conta demo",
                        "saldo": saldo_atual,
                        "tipo_conta": "demo",
                        "conta_id": resultado.get("conta_id", ""),
                    }
                )
            else:
                return (
                    jsonify({"status": "erro", "mensagem": "Token demo inválido"}),
                    400,
                )

        elif tipo == "real" and licenca_atual.get("token_deriv_real"):
            # Troca para conta real
            token = licenca_atual["token_deriv_real"]
            valido, resultado = verificar_token(token)

            if valido:
                session["token"] = token
                session["tipo_conta"] = "real"

                # Usa o ID da conta real da licença se disponível
                if licenca_atual.get("deriv_real"):
                    session["deriv_account"] = licenca_atual["deriv_real"]
                else:
                    session["deriv_account"] = resultado.get("conta_id", "")

                # Reinicializa a API
                inicializar_api(token)

                # Aguarda um pouco para a conexão estabelecer
                time.sleep(1)

                # Obtém saldo real da API
                if deriv_api and deriv_api.conectado and hasattr(deriv_api, "saldo"):
                    saldo_atual = deriv_api.saldo
                else:
                    saldo_atual = resultado.get("saldo", 0)

                session["saldo"] = saldo_atual
                lucro_atual = 0.0  # Reset do lucro ao trocar conta

                return jsonify(
                    {
                        "status": "ok",
                        "mensagem": "Trocado para conta real",
                        "saldo": saldo_atual,
                        "tipo_conta": "real",
                        "conta_id": resultado.get("conta_id", ""),
                    }
                )
            else:
                return (
                    jsonify({"status": "erro", "mensagem": "Token real inválido"}),
                    400,
                )
        else:
            return (
                jsonify({"status": "erro", "mensagem": f"Token {tipo} não disponível"}),
                400,
            )

    except Exception as e:
        logger.error(f"Erro ao trocar conta: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/status_deriv")
def status_deriv():
    """Rota para verificar status da conexão com Deriv"""
    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        if deriv_api:
            resultado = deriv_api.verificar_conexao()
            return jsonify(resultado)
        else:
            return jsonify({"status": "erro", "mensagem": "API não inicializada"})
    except Exception as e:
        logger.error(f"Erro ao verificar status Deriv: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/saldo_atual")
def saldo_atual():
    """Rota para obter saldo atual"""
    global saldo_atual

    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        # SEMPRE tenta obter saldo real da API primeiro
        if deriv_api and deriv_api.conectado:
            # Usa o saldo já capturado na autorização
            if hasattr(deriv_api, "saldo") and deriv_api.saldo > 0:
                saldo_atual = deriv_api.saldo
                session["saldo"] = saldo_atual
                return {"status": "ok", "saldo": saldo_atual}

            # Se não tem saldo, tenta obter via requisição
            resultado = deriv_api.obter_saldo()
            if resultado["status"] == "ok":
                saldo_atual = resultado["saldo"]
                session["saldo"] = saldo_atual
                return resultado

        # Se não há API conectada, tenta reconectar
        if session.get("token"):
            token_atual = session["token"]
            if not deriv_api or not deriv_api.conectado:
                inicializar_api(token_atual)

            # Tenta novamente após reconexão
            if deriv_api and deriv_api.conectado and hasattr(deriv_api, "saldo"):
                saldo_atual = deriv_api.saldo
                session["saldo"] = saldo_atual
                return {"status": "ok", "saldo": saldo_atual}

        # Como último recurso, usa verificação de token
        valido, dados_token = verificar_token(session["token"])
        if valido and "saldo" in dados_token:
            saldo_atual = dados_token["saldo"]
            session["saldo"] = saldo_atual
            return {"status": "ok", "saldo": saldo_atual}
        else:
            # Se tudo falhar, retorna saldo 0
            return {"status": "ok", "saldo": 0.0}

    except Exception as e:
        logger.error(f"Erro ao obter saldo: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/adicionar_token", methods=["POST"])
def adicionar_token():
    """Rota para adicionar um novo token (demo ou real)"""
    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        data = request.get_json()
        tipo = data.get("tipo")
        token = data.get("token")

        if tipo not in ["demo", "real"]:
            return (
                jsonify({"status": "erro", "mensagem": "Tipo de token inválido"}),
                400,
            )

        if not token or len(token.strip()) < 5:
            return jsonify({"status": "erro", "mensagem": "Token inválido"}), 400

        # Verifica se o token é válido
        valido, _ = verificar_token(token.strip())
        if not valido:
            return (
                jsonify(
                    {"status": "erro", "mensagem": "Token inválido ou não funcional"}
                ),
                400,
            )

        # Atualiza a licença
        if "codigo_licenca" not in session:
            return jsonify({"status": "erro", "mensagem": "Sessão inválida"}), 400

        licencas = carregar_licencas()
        licenca_atualizada = False

        for key, licenca in licencas.items():
            if licenca.get("codigo_licenca") == session["codigo_licenca"]:
                if tipo == "demo":
                    licenca["token_deriv_demo"] = token.strip()
                    session["token_demo"] = token.strip()
                else:
                    licenca["token_deriv_real"] = token.strip()
                    session["token_real"] = token.strip()
                licencas[key] = licenca
                licenca_atualizada = True
                break

        if not licenca_atualizada:
            return (
                jsonify({"status": "erro", "mensagem": "Licença não encontrada"}),
                400,
            )

        salvar_licencas(licencas)

        return jsonify(
            {"status": "ok", "mensagem": f"Token {tipo} adicionado com sucesso"}
        )

    except Exception as e:
        logger.error(f"Erro ao adicionar token: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/historico")
def historico():
    """Rota para obter histórico de operações"""
    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        return jsonify({"status": "ok", "historico": historico_operacoes})
    except Exception as e:
        logger.error(f"Erro ao obter histórico: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/limpar_historico", methods=["POST"])
def limpar_historico():
    """Rota para limpar histórico de operações"""
    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        global historico_operacoes, contador_operacoes, lucro_atual
        historico_operacoes = []
        contador_operacoes = 0
        lucro_atual = 0.0
        salvar_historico()

        return jsonify({"status": "ok", "mensagem": "Histórico limpo com sucesso"})
    except Exception as e:
        logger.error(f"Erro ao limpar histórico: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/status_detalhado")
def status_detalhado():
    """Rota para obter status detalhado do robô"""
    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        return jsonify(
            {
                "ativo": robo_ativo,
                "modo": modo_operacao,
                "meta": meta_diaria,
                "lucro": lucro_atual,
                "saldo": saldo_atual,
                "operacoes": contador_operacoes,
                "status_operacao": status_operacao,
                "mensagem_log": ultima_mensagem,
                "historico_recente": (
                    historico_operacoes[-5:] if historico_operacoes else []
                ),
            }
        )
    except Exception as e:
        logger.error(f"Erro ao obter status detalhado: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/api/grafico/dados")
def api_grafico_dados():
    """Rota para obter dados do gráfico"""
    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        # Simula dados de gráfico
        return jsonify(
            {
                "status": "ok",
                "dados": {
                    "labels": ["00:00", "01:00", "02:00", "03:00", "04:00"],
                    "valores": [100, 105, 98, 110, 115],
                },
            }
        )
    except Exception as e:
        logger.error(f"Erro ao obter dados do gráfico: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/api/historico/estatisticas")
def api_historico_estatisticas():
    """Rota para obter estatísticas do histórico"""
    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        if not historico_operacoes:
            return jsonify(
                {
                    "status": "ok",
                    "estatisticas": {
                        "total_operacoes": 0,
                        "operacoes_ganho": 0,
                        "operacoes_perda": 0,
                        "assertividade": 0,
                        "lucro_total": 0,
                        "media_lucro": 0,
                    },
                }
            )

        total_operacoes = len(historico_operacoes)
        operacoes_ganho = sum(
            1 for op in historico_operacoes if op.get("resultado_real", 0) > 0
        )
        operacoes_perda = sum(
            1 for op in historico_operacoes if op.get("resultado_real", 0) < 0
        )
        lucro_total = sum(op.get("resultado_real", 0) for op in historico_operacoes)
        assertividade = (
            (operacoes_ganho / total_operacoes * 100) if total_operacoes > 0 else 0
        )
        media_lucro = lucro_total / total_operacoes if total_operacoes > 0 else 0

        return jsonify(
            {
                "status": "ok",
                "estatisticas": {
                    "total_operacoes": total_operacoes,
                    "operacoes_ganho": operacoes_ganho,
                    "operacoes_perda": operacoes_perda,
                    "assertividade": assertividade,
                    "lucro_total": lucro_total,
                    "media_lucro": media_lucro,
                },
            }
        )
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# Sistema de operações movido para motor.py e catalogador.py


# Função para restaurar sessão automaticamente
def restaurar_sessao():
    """Tenta restaurar a sessão automaticamente usando licenças"""
    try:
        # Verifica se há uma licença válida para autenticação automática
        licenca_auto = verificar_autenticacao_automatica()
        if licenca_auto:
            token_real, token_demo = obter_tokens_da_licenca(licenca_auto)
            token_principal = token_real if token_real else token_demo

            if token_principal:
                valido, _ = verificar_token(token_principal)
                if valido:
                    inicializar_api(token_principal)
                    logger.info(
                        f"Sessão restaurada automaticamente para licença {licenca_auto.get('codigo_licenca')}"
                    )
                    return True

        logger.info("Nenhuma sessão válida encontrada para restauração automática")
        return False

    except Exception as e:
        logger.error(f"Erro ao restaurar sessão: {e}")
        return False


# Tenta restaurar a sessão ao iniciar
restaurar_sessao()


# Função para inicializar o servidor
def iniciar_servidor():
    """Inicializa o servidor Flask"""
    # Carrega o histórico
    carregar_historico()

    # Inicia o servidor Flask
    app.run(host="0.0.0.0", port=5000, debug=False)


# Execução principal
if __name__ == "__main__":
    iniciar_servidor()
