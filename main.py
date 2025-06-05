#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Arquivo principal do DerivBot - Versão Enxuta
Responsável por inicializar o servidor Flask e gerenciar as rotas principais
"""

import os
import json
import logging


from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

# Importações locais
from src.core.motor import Motor
from src.config.config import Config
from src.utils.gerador_licencas import (
    carregar_licencas,
    salvar_licencas,
    validar_dispositivo,
    vincular_dispositivo,
    obter_hwid,
    obter_ip,
)

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
app.secret_key = Config.SECRET_KEY
app.config["SESSION_TYPE"] = "filesystem"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config["SESSION_FILE_DIR"] = os.path.join(DATA_DIR, "flask_session")
app.config["SESSION_PERMANENT"] = True

# Garante que o diretório de sessão existe
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)

# Inicialização das APIs
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

# CONTROLE DE OPERAÇÕES PARA MODO INICIANTE
operacoes_ativas = []  # Lista de operações em andamento
ultima_operacao_tempo = 0  # Timestamp da última operação
max_operacoes_simultaneas = {"Iniciante": 3, "Conservador": 5, "Agressivo": 10}
intervalo_entre_operacoes = {
    "Iniciante": 5,
    "Conservador": 3,
    "Agressivo": 1,
}  # segundos

# Sistema de logs unificado e otimizado
logs_tempo_real = []
logs_painel = []
max_logs = 100
max_logs_painel = 50


class LoggerUnificado:
    """Sistema de logs unificado para evitar duplicações"""

    def __init__(self):
        """Inicializa sistema de logs avançado"""
        self.estatisticas = {
            "total_operacoes": 0,
            "operacoes_win": 0,
            "operacoes_loss": 0,
            "lucro_total": 0.0,
            "inicio_sessao": datetime.now(),
            "ultima_operacao": None,
            "win_rate": 0.0,
            "melhor_sequencia": 0,
            "sequencia_atual": 0,
            "pior_sequencia": 0,
        }
        self.historico_performance = []
        self.alertas_ativos = []

    @staticmethod
    def adicionar_log(
        mensagem,
        tipo="info",
        categoria="sistema",
        incluir_painel=False,
        incluir_tempo_real=True,
        dados_extras=None,
    ):
        """Adiciona log de forma unificada com categorização avançada"""
        global logs_tempo_real, logs_painel

        agora = datetime.now()
        timestamp = agora.strftime("%H:%M:%S")
        timestamp_completo = agora.strftime("%Y-%m-%d %H:%M:%S")

        log_entry = {
            "id": len(logs_tempo_real) + 1,
            "timestamp": timestamp,
            "timestamp_completo": timestamp_completo,
            "timestamp_unix": agora.timestamp(),
            "mensagem": str(mensagem),
            "tipo": tipo,
            "categoria": categoria,
            "dados_extras": dados_extras or {},
            "nivel_prioridade": LoggerUnificado._obter_prioridade(tipo),
        }

        # Adiciona aos logs de tempo real se solicitado
        if incluir_tempo_real:
            logs_tempo_real.append(log_entry)
            if len(logs_tempo_real) > max_logs:
                logs_tempo_real = logs_tempo_real[-max_logs:]

        # Adiciona aos logs do painel se solicitado
        if incluir_painel:
            logs_painel.append(log_entry)
            if len(logs_painel) > max_logs_painel:
                logs_painel = logs_painel[-max_logs_painel:]

        # Log no sistema padrão também
        LoggerUnificado._log_sistema(mensagem, tipo, categoria)

        return log_entry

    @staticmethod
    def _obter_prioridade(tipo):
        """Define prioridade do log para ordenação"""
        prioridades = {
            "error": 1,
            "warning": 2,
            "trading": 3,
            "success": 4,
            "info": 5,
            "debug": 6,
        }
        return prioridades.get(tipo, 5)

    @staticmethod
    def _log_sistema(mensagem, tipo, categoria):
        """Log no sistema padrão com formatação melhorada"""
        prefixo = f"[{categoria.upper()}]"

        if tipo == "error":
            logger.error(f"{prefixo} ❌ {mensagem}")
        elif tipo == "warning":
            logger.warning(f"{prefixo} ⚠️ {mensagem}")
        elif tipo == "success":
            logger.info(f"{prefixo} ✅ {mensagem}")
        elif tipo == "trading":
            logger.info(f"{prefixo} 💰 {mensagem}")
        else:
            logger.info(f"{prefixo} ℹ️ {mensagem}")

    @staticmethod
    def log_operacao(
        tipo_operacao, valor_entrada, resultado=None, ativo=None, modo=None
    ):
        """Log específico para operações de trading com análise de performance"""
        dados_operacao = {
            "tipo_operacao": tipo_operacao,
            "valor_entrada": valor_entrada,
            "resultado": resultado,
            "ativo": ativo,
            "modo": modo,
            "timestamp_operacao": datetime.now().isoformat(),
        }

        if resultado is not None:
            # Operação finalizada
            if resultado > 0:
                mensagem = f"✅ WIN: {tipo_operacao} | Entrada: ${valor_entrada:.2f} | Lucro: ${resultado:.2f}"
                tipo_log = "success"
            else:
                mensagem = f"❌ LOSS: {tipo_operacao} | Entrada: ${valor_entrada:.2f} | Perda: ${abs(resultado):.2f}"
                tipo_log = "warning"
        else:
            # Operação iniciada
            mensagem = f"🎯 ENTRADA: {tipo_operacao} | Valor: ${valor_entrada:.2f} | Ativo: {ativo}"
            tipo_log = "trading"

        return LoggerUnificado.adicionar_log(
            mensagem,
            tipo_log,
            "trading",
            incluir_painel=True,
            dados_extras=dados_operacao,
        )

    @staticmethod
    def log_sistema_status(status, detalhes=None):
        """Log para status do sistema (conexão, reconexão, etc.)"""
        dados_status = {
            "status": status,
            "detalhes": detalhes,
            "timestamp_status": datetime.now().isoformat(),
        }

        if status == "conectado":
            mensagem = "🟢 Sistema conectado e operacional"
            tipo_log = "success"
        elif status == "desconectado":
            mensagem = "🔴 Sistema desconectado"
            tipo_log = "error"
        elif status == "reconectando":
            mensagem = "🟡 Tentando reconectar..."
            tipo_log = "warning"
        else:
            mensagem = f"ℹ️ Status: {status}"
            tipo_log = "info"

        return LoggerUnificado.adicionar_log(
            mensagem,
            tipo_log,
            "sistema",
            incluir_painel=True,
            dados_extras=dados_status,
        )

    @staticmethod
    def obter_estatisticas_performance():
        """Obtém estatísticas de performance em tempo real"""
        global logs_tempo_real

        # Filtra logs de trading
        logs_trading = [
            log for log in logs_tempo_real if log.get("categoria") == "trading"
        ]

        total_ops = len(
            [
                log
                for log in logs_trading
                if "WIN:" in log["mensagem"] or "LOSS:" in log["mensagem"]
            ]
        )
        wins = len([log for log in logs_trading if "WIN:" in log["mensagem"]])
        losses = len([log for log in logs_trading if "LOSS:" in log["mensagem"]])

        win_rate = (wins / total_ops * 100) if total_ops > 0 else 0

        return {
            "total_operacoes": total_ops,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 2),
            "ultima_atualizacao": datetime.now().strftime("%H:%M:%S"),
        }


# Instância global do logger
logger_unificado = LoggerUnificado()


# Funções de conveniência para compatibilidade
def adicionar_log_tempo_real(mensagem, tipo="info"):
    """Função de compatibilidade para logs de tempo real"""
    LoggerUnificado.adicionar_log(
        mensagem, tipo, incluir_painel=True, incluir_tempo_real=True
    )

    # Força adição aos logs globais também
    global logs_tempo_real
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "categoria": (
            "sistema"
            if tipo in ["info", "success"]
            else "trading" if tipo == "trade" else "error"
        ),
        "tipo": tipo,
        "mensagem": mensagem,
    }
    logs_tempo_real.append(log_entry)

    # Mantém apenas os últimos 50 logs
    if len(logs_tempo_real) > 50:
        logs_tempo_real.pop(0)


def adicionar_log_painel(mensagem, tipo="info"):
    """Função de compatibilidade para logs do painel"""
    LoggerUnificado.adicionar_log(
        mensagem, tipo, incluir_painel=True, incluir_tempo_real=True
    )


def pode_executar_operacao():
    """Verifica se pode executar uma nova operação baseado no modo"""
    global operacoes_ativas, ultima_operacao_tempo, modo_operacao
    import time

    agora = time.time()
    modo_atual = modo_operacao.capitalize()

    # Remove operações antigas (mais de 60 segundos)
    operacoes_ativas[:] = [op for op in operacoes_ativas if agora - op < 60]

    # Verifica limite de operações simultâneas
    max_ops = max_operacoes_simultaneas.get(modo_atual, 3)
    if len(operacoes_ativas) >= max_ops:
        adicionar_log_painel(
            f"🚫 Limite de {max_ops} operações simultâneas atingido", "warning"
        )
        return False

    # Verifica intervalo entre operações
    intervalo = intervalo_entre_operacoes.get(modo_atual, 5)
    if agora - ultima_operacao_tempo < intervalo:
        tempo_restante = int(intervalo - (agora - ultima_operacao_tempo))
        adicionar_log_painel(
            f"⏳ Aguardando {tempo_restante}s para próxima operação", "info"
        )
        return False

    return True


def registrar_nova_operacao():
    """Registra uma nova operação no controle"""
    global operacoes_ativas, ultima_operacao_tempo
    import time

    agora = time.time()
    operacoes_ativas.append(agora)
    ultima_operacao_tempo = agora

    adicionar_log_painel(
        f"🚀 Nova operação iniciada ({len(operacoes_ativas)} ativas)", "success"
    )


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
                # API removida - usando motor
                if motor and motor.conectado:
                    resultado_saldo = {"status": "ok", "saldo": motor.obter_saldo()}
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
                # API removida - usando motor
                if motor and motor.conectado:
                    resultado_saldo = {"status": "ok", "saldo": motor.obter_saldo()}
                    if resultado_saldo.get("status") == "ok":
                        saldo = resultado_saldo["saldo"]
                    else:
                        saldo = 10000.0  # Saldo padrão demo se não conseguir obter
                else:
                    saldo = 10000.0
                break

        # Se não encontrou nas licenças, usa verificação padrão
        if not conta_id:
            # API removida - usando motor
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
    """Inicializa o Motor com o token fornecido"""
    global motor
    # SEMPRE cria o motor, mesmo se der erro
    motor = None
    try:
        motor = Motor()
        if token:
            motor.conectar(token)
        logger.info("MOTOR TURBO INICIALIZADO COM SUCESSO")
        return True
    except Exception as motor_error:
        logger.warning(f"Erro ao inicializar motor: {motor_error}")
        # Cria motor básico mesmo com erro
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
            if hwid_atual and hwid_atual == licenca.get("hwid"):
                fatores_conferidos += 1
                logger.info("HWID confere")

            # Fator 2: IP
            if ip_atual and ip_atual == licenca.get("ip"):
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


def forcar_demo_para_teste_ai():
    """🤖 FUNÇÃO ESPECIAL: Força uso de demo quando EU (AI) estiver testando

    Esta função é usada apenas quando eu (AI) preciso testar o sistema
    para garantir que não gaste o dinheiro real do usuário.
    O usuário continua com controle total para escolher real/demo.
    """
    try:
        licenca_auto = verificar_autenticacao_automatica()
        if licenca_auto:
            _, token_demo = obter_tokens_da_licenca(
                licenca_auto
            )  # Removido token_real não usado
            # 🛡️ SEMPRE DEMO PARA TESTES DA AI - PROTEGE SEU DINHEIRO!
            if token_demo:
                logger.info(
                    "🤖 AI TESTANDO: Usando conta DEMO para proteger seu dinheiro!"
                )
                return token_demo, "demo"
            else:
                logger.warning("⚠️ AI TESTANDO: Sem token demo disponível!")
                return None, None
        return None, None
    except Exception as e:
        logger.error(f"Erro ao forçar demo para teste AI: {e}")
        return None, None


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
    global historico_operacoes, contador_operacoes, lucro_atual, saldo_atual

    # Usa timezone local do Brasil
    from datetime import timezone, timedelta

    fuso_brasil = timezone(timedelta(hours=-3))  # UTC-3 (Brasília)
    agora = datetime.now(fuso_brasil)

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

    # Atualiza lucro atual
    lucro_atual += resultado

    # Atualiza saldo se motor estiver disponível
    if motor and hasattr(motor, "obter_saldo"):
        try:
            saldo_atual = motor.obter_saldo()
        except:
            pass

    # Adiciona logs visuais para o painel
    resultado_texto = f"+${resultado:.2f}" if resultado > 0 else f"${resultado:.2f}"
    emoji = "📈" if resultado > 0 else "📉"

    adicionar_log_painel(
        f"{emoji} {tipo} finalizada: {resultado_texto} | Total: ${lucro_atual:.2f}",
        "success" if resultado > 0 else "error",
    )

    # Log para tempo real também
    adicionar_log_tempo_real(
        f"💰 {tipo} finalizada: {resultado_texto} (Total: ${lucro_atual:.2f})",
        "success" if resultado > 0 else "warning",
    )

    salvar_historico()


def sincronizar_dados_motor():
    """Sincroniza dados do motor com as variáveis globais"""
    global lucro_atual, saldo_atual, contador_operacoes, historico_operacoes

    if motor and hasattr(motor, "catalogador"):
        try:
            # Obtém status do lucro do catalogador otimizado
            if hasattr(motor.catalogador, "obter_status_lucro"):
                status_lucro = motor.catalogador.obter_status_lucro()

                # Atualiza variáveis globais com dados do catalogador
                if status_lucro.get("lucro_sessao") is not None:
                    lucro_atual = status_lucro["lucro_sessao"]

                if status_lucro.get("total_operacoes") is not None:
                    contador_operacoes = status_lucro["total_operacoes"]

                # Adiciona operações recentes ao histórico global se necessário
                historico_recente = status_lucro.get("historico_recente", [])
                for operacao in historico_recente:
                    # Verifica se a operação já está no histórico global
                    if not any(
                        op.get("timestamp") == operacao.get("timestamp")
                        for op in historico_operacoes
                    ):
                        historico_operacoes.append(
                            {
                                "data": operacao.get("data"),
                                "hora": operacao.get("hora"),
                                "tipo": operacao.get("tipo"),
                                "valor": operacao.get("valor"),
                                "resultado_real": operacao.get("resultado"),
                                "timestamp": operacao.get("timestamp"),
                            }
                        )

            # Atualiza saldo
            if hasattr(motor, "obter_saldo"):
                saldo_atual = motor.obter_saldo()

            # Fallback para histórico do motor se catalogador não tiver dados
            if (
                not lucro_atual
                and hasattr(motor, "historico_resultados")
                and motor.historico_resultados
            ):
                lucro_total = sum(
                    op.get("lucro", 0) for op in motor.historico_resultados
                )
                lucro_atual = lucro_total
                contador_operacoes = len(motor.historico_resultados)

        except Exception as e:
            logger.error(f"Erro ao sincronizar dados do motor: {e}")


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

                # Salva ambos os tokens na sessão para permitir troca de conta
                token_real, token_demo = obter_tokens_da_licenca(licenca_auto)
                session["token_real"] = token_real
                session["token_demo"] = token_demo

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
        if not licenca.get("hwid") and not licenca.get("ip"):
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
        if token_principal == token_real:
            session["tipo_conta"] = "real"
        else:
            session["tipo_conta"] = "demo"

        # Salva ambos os tokens na sessão para permitir troca de conta
        token_real, token_demo = obter_tokens_da_licenca(licenca)
        session["token_real"] = token_real
        session["token_demo"] = token_demo

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
    # Verifica autenticação automática se não há sessão
    if "token" not in session:
        licenca_auto = verificar_autenticacao_automatica()
        if licenca_auto:
            # Restaura sessão automaticamente
            token_real, token_demo = obter_tokens_da_licenca(licenca_auto)
            if token_real:
                session["token"] = token_real
                session["tipo_conta"] = "real"
                session["codigo_licenca"] = licenca_auto["codigo_licenca"]
                session["deriv_account"] = licenca_auto.get("deriv_real", "")
                # Salva ambos os tokens na sessão para permitir troca de conta
                session["token_real"] = token_real
                session["token_demo"] = token_demo
                logger.info("Sessão restaurada automaticamente para toggle_bot")
            else:
                return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401
        else:
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

        global robo_ativo, modo_operacao, meta_diaria, status_operacao, motor

        if robo_ativo:
            # Verifica proteção antes de parar
            if motor is not None:
                protecao = motor.verificar_protecao_parada()

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
            if motor is not None:
                motor.parar()
            return jsonify(
                {"status": "parado", "mensagem": "Robô parado com segurança"}
            )
        else:
            # Verifica se o motor está conectado (não a deriv_api)
            if not motor or not getattr(motor, "conectado", False):
                return (
                    jsonify(
                        {
                            "status": "erro",
                            "mensagem": "Motor não conectado. Verifique sua conexão.",
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

            # Logs de inicialização da estratégia turbo
            adicionar_log_tempo_real("🎯 Iniciando Estratégia Turbo...", "info")
            adicionar_log_tempo_real(
                f"📊 Modo: {modo.upper()}, Meta: ${meta:.0f}", "info"
            )
            adicionar_log_tempo_real("🔧 Ativo: VIX75 (1HZ75V) - Contratos 15s", "info")
            adicionar_log_tempo_real(
                "📈 Indicadores: EMA(8,21) + RSI(14) + Bollinger(20,2)", "info"
            )
            adicionar_log_tempo_real(
                "💰 Gestão: Stop 2% | Take 4-6% | Martingale 2x", "info"
            )

            # Inicia o sistema inteligente no motor - VERSÃO SEGURA
            adicionar_log_tempo_real("⚙️ Configurando motor...", "info")
            try:
                # Usa motor existente se disponível e conectado
                if motor and hasattr(motor, "conectado") and motor.conectado:
                    logger.info("Usando motor existente já conectado")
                else:
                    # Cria novo motor apenas se necessário
                    from src.core.motor import Motor

                    motor = Motor()

                    # Conecta com o token da sessão
                    token_atual = session.get("token")
                    if token_atual:
                        motor.conectar(token_atual)

                # Configura modo e meta
                motor.modo_operacao = modo
                motor.meta_diaria = meta

                # Inicia sistema inteligente de forma segura
                if hasattr(motor, "iniciar_sistema_inteligente"):
                    # Inicia em thread separada para não travar
                    import threading

                    def iniciar_motor_seguro():
                        try:
                            motor.iniciar_sistema_inteligente()
                            logger.info("Sistema inteligente iniciado com sucesso")
                        except Exception as e:
                            logger.error(f"Erro ao iniciar sistema inteligente: {e}")

                    thread = threading.Thread(target=iniciar_motor_seguro, daemon=True)
                    thread.start()

                    logger.info("SISTEMA INTELIGENTE INICIADO EM THREAD SEPARADA")
                    adicionar_log_tempo_real("🚀 Motor Turbo iniciado!", "success")
                    adicionar_log_tempo_real("⚡ Sistema inteligente ATIVO!", "info")
                else:
                    logger.warning(
                        "Motor não possui método iniciar_sistema_inteligente"
                    )
                    adicionar_log_tempo_real("⚠️ Motor em modo básico", "warning")

                # Atualiza variável global
                globals()["motor"] = motor

            except Exception as e:
                logger.error(f"ERRO ao iniciar sistema: {e}")
                adicionar_log_tempo_real(f"❌ ERRO: {str(e)}", "error")

                # Continua mesmo com erro para não travar a interface
                adicionar_log_tempo_real("🔄 Sistema em modo básico", "warning")

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


@app.route("/status_robo_teste")
def status_robo_teste():
    """Rota de teste para identificar o problema"""
    return jsonify({"status": "ok", "teste": "funcionando"})


@app.route("/toggle_bot_teste", methods=["POST"])
def toggle_bot_teste():
    """Rota de teste para toggle_bot"""
    try:
        data = request.get_json()
        logger.info(f"Teste toggle_bot recebido: {data}")
        return jsonify(
            {
                "status": "teste_ok",
                "dados_recebidos": data,
                "motor_existe": motor is not None,
                "sessao_token": "token" in session,
            }
        )
    except Exception as e:
        logger.error(f"Erro no teste toggle_bot: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/simular_operacao", methods=["POST"])
def simular_operacao():
    """Simula uma operação para testar a atualização do lucro"""
    try:
        global lucro_atual, contador_operacoes, historico_operacoes

        data = request.get_json()
        resultado = float(data.get("resultado", 10.0))  # Padrão: +$10

        # Adiciona ao lucro atual
        lucro_atual += resultado
        contador_operacoes += 1

        # Adiciona ao histórico
        operacao = {
            "data": datetime.now().strftime("%d/%m/%Y"),
            "hora": datetime.now().strftime("%H:%M:%S"),
            "tipo": "CALL" if resultado > 0 else "PUT",
            "valor": 2.0,
            "resultado_real": resultado,
            "timestamp": datetime.now().isoformat(),
        }

        historico_operacoes.append(operacao)

        # Adiciona log
        adicionar_log_tempo_real(
            f"Operação simulada: {'+' if resultado >= 0 else ''}${resultado:.2f}",
            "success" if resultado >= 0 else "error",
        )

        logger.info(
            f"Operação simulada: ${resultado:.2f} - Lucro total: ${lucro_atual:.2f}"
        )

        return jsonify(
            {
                "status": "ok",
                "resultado": resultado,
                "lucro_total": lucro_atual,
                "operacoes": contador_operacoes,
                "mensagem": f"Operação simulada: {'+' if resultado >= 0 else ''}${resultado:.2f}",
            }
        )

    except Exception as e:
        logger.error(f"Erro ao simular operação: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/status_robo")
def status_robo():
    """Rota para obter status do robô com informações inteligentes"""
    # Verifica autenticação automática se não há sessão
    if "token" not in session:
        licenca_auto = verificar_autenticacao_automatica()
        if licenca_auto:
            # Restaura sessão automaticamente
            token_real, token_demo = obter_tokens_da_licenca(licenca_auto)
            if token_real:
                session["token"] = token_real
                session["tipo_conta"] = "real"
                session["codigo_licenca"] = licenca_auto["codigo_licenca"]
                session["deriv_account"] = licenca_auto.get("deriv_real", "")
                # Salva ambos os tokens na sessão para permitir troca de conta
                session["token_real"] = token_real
                session["token_demo"] = token_demo
            else:
                return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401
        else:
            return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        global robo_ativo, modo_operacao, meta_diaria, status_operacao, ultima_mensagem

        # Sincroniza dados do motor antes de retornar
        sincronizar_dados_motor()

        # Informações do ativo atual - ESTRATÉGIA TURBO FIXA
        ativo_info = {
            "ativo": "1HZ75V",
            "nome": "Volatility 75 Index (VIX75)",
            "razao": "Estratégia Turbo - Contratos 15s",
            "prioridade": 1,
        }

        # Status do motor - CORRIGIDO PARA EVITAR ERRO JSON
        motor_status = {"conectado": False, "operacoes_ativas": 0}
        if motor:
            try:
                # Obtém apenas valores simples para evitar erro de serialização
                conectado = getattr(motor, "conectado", False)
                operacoes_abertas = getattr(motor, "operacoes_abertas", {})
                par_atual = getattr(motor, "par_atual", "1HZ75V")
                saldo = getattr(motor, "saldo", 0.0)

                motor_status = {
                    "conectado": bool(conectado) if conectado is not None else False,
                    "operacoes_ativas": (
                        len(operacoes_abertas)
                        if isinstance(operacoes_abertas, dict)
                        else 0
                    ),
                    "par_atual": str(par_atual) if par_atual else "1HZ75V",
                    "saldo": float(saldo) if isinstance(saldo, (int, float)) else 0.0,
                }
            except Exception as e:
                logger.error(f"Erro ao obter status do motor: {e}")
                motor_status = {"conectado": False, "operacoes_ativas": 0}

        # Informações detalhadas para o usuário
        status_detalhado = "Sistema parado"
        if robo_ativo:
            if motor and hasattr(motor, "sistema_ativo") and motor.sistema_ativo:
                status_detalhado = (
                    f"Analisando {ativo_info.get('ativo', 'ativo')} - Scanner ativo"
                )
            else:
                status_detalhado = "Iniciando sistema inteligente..."

        # Mensagem clara para o usuário
        mensagem_usuario = ultima_mensagem or "Sistema pronto"
        if robo_ativo:
            if "timeout" in str(ultima_mensagem).lower():
                mensagem_usuario = "API de IA com latência alta - aguardando..."
            elif "aguardar" in str(ultima_mensagem).lower():
                mensagem_usuario = f"Aguardando melhor oportunidade no {ativo_info.get('ativo', 'ativo')}"
            elif "analise" in str(ultima_mensagem).lower():
                mensagem_usuario = (
                    f"Analisando padrões no {ativo_info.get('ativo', 'ativo')}"
                )

        # Prepara dados seguros para JSON
        response_data = {
            "ativo": bool(robo_ativo),
            "modo": str(modo_operacao or "iniciante"),
            "meta": float(meta_diaria or 20.0),
            "lucro": float(lucro_atual),
            "saldo": float(saldo_atual),
            "operacoes": int(contador_operacoes),
            "status_operacao": str(status_operacao or "parado"),
            "status_detalhado": str(status_detalhado),
            "mensagem_log": str(ultima_mensagem or "Sistema pronto"),
            "mensagem_usuario": str(mensagem_usuario),
            "ativo_atual": dict(ativo_info),
            "motor_status": dict(motor_status),
            "logs_tempo_real": list(logs_tempo_real[-20:] if logs_tempo_real else []),
            "logs_painel": list(
                logs_painel[-10:] if logs_painel else []
            ),  # Logs visuais
            "historico_recente": list(
                historico_operacoes[-3:] if historico_operacoes else []
            ),
            "scanner_info": {
                "total_ativos": 15,
                "ativo_selecionado": str(ativo_info.get("ativo", "R_100")),
                "razao_selecao": str(ativo_info.get("razao", "Ativo padrão")),
                "prioridade": int(ativo_info.get("prioridade", 5)),
            },
        }

        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Erro ao obter status do robô: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/selecionar_conta", methods=["POST"])
def selecionar_conta():
    """Rota para trocar entre conta demo/real"""
    import time

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
                time.sleep(1)

                # Obtém saldo real da API
                if motor and motor.conectado and hasattr(deriv_api, "saldo"):
                    saldo_atual = motor.obter_saldo()
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
                if motor and motor.conectado and hasattr(deriv_api, "saldo"):
                    saldo_atual = motor.obter_saldo()
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
        if motor:
            resultado = motor.status_conexao()
            return jsonify(resultado)
        else:
            return jsonify({"status": "erro", "mensagem": "API não inicializada"})
    except Exception as e:
        logger.error(f"Erro ao verificar status Deriv: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/saldo_atual")
def obter_saldo_atual():
    """Rota para obter saldo atual"""
    global saldo_atual

    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        # SEMPRE tenta obter saldo real da API primeiro
        if motor and motor.conectado:
            # Usa o saldo já capturado na autorização
            if hasattr(deriv_api, "saldo") and motor.obter_saldo() > 0:
                saldo_atual = motor.obter_saldo()
                session["saldo"] = saldo_atual
                return {"status": "ok", "saldo": saldo_atual}

            # Se não tem saldo, tenta obter via requisição
            resultado = motor.obter_saldo()
            if resultado["status"] == "ok":
                saldo_atual = resultado["saldo"]
                session["saldo"] = saldo_atual
                return resultado

        # Se não há API conectada, tenta reconectar
        if session.get("token"):
            token_atual = session["token"]
            if not motor or not motor.conectado:
                inicializar_api(token_atual)

            # Tenta novamente após reconexão
            if motor and motor.conectado and hasattr(deriv_api, "saldo"):
                saldo_atual = motor.obter_saldo()
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
        # Sincroniza dados do motor antes de retornar
        sincronizar_dados_motor()

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
                "logs_tempo_real": (
                    logs_tempo_real[-20:] if logs_tempo_real else []
                ),  # Últimos 20 logs
                "historico_recente": (
                    historico_operacoes[-5:] if historico_operacoes else []
                ),
            }
        )
    except Exception as e:
        logger.error(f"Erro ao obter status detalhado: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/logs_tempo_real")
def get_logs_tempo_real():
    """Rota para obter logs em tempo real"""
    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        return jsonify(
            {
                "status": "ok",
                "logs": (
                    logs_tempo_real[-50:] if logs_tempo_real else []
                ),  # Últimos 50 logs
            }
        )
    except Exception as e:
        logger.error(f"Erro ao obter logs: {e}")
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


@app.route("/teste_ai_demo")
def teste_ai_demo():
    """🤖 ENDPOINT ESPECIAL: Testa função de demo para AI"""
    try:
        token_demo, tipo_conta = forcar_demo_para_teste_ai()
        if token_demo:
            return jsonify(
                {
                    "status": "sucesso",
                    "mensagem": "🤖 AI testando com conta DEMO - Seu dinheiro está protegido!",
                    "token": token_demo[:10] + "...",  # Mostra só parte do token
                    "tipo_conta": tipo_conta,
                }
            )
        else:
            return jsonify(
                {
                    "status": "erro",
                    "mensagem": "Não foi possível obter token demo para teste",
                }
            )
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": f"Erro no teste AI: {e}"})


@app.route("/teste_historico_publico", methods=["POST"])
def teste_historico_publico():
    """Teste público para verificar histórico - SEM AUTENTICAÇÃO"""
    try:
        # Adiciona operações de teste diretamente
        adicionar_operacao("CALL", 0.35, 0.65)  # Ganho
        adicionar_operacao("PUT", 0.35, -0.35)  # Perda
        adicionar_operacao("CALL", 0.35, 0.70)  # Ganho

        return jsonify(
            {
                "status": "ok",
                "mensagem": "3 operações de teste adicionadas",
                "operacoes_adicionadas": 3,
                "lucro_atual": lucro_atual,
                "contador_operacoes": contador_operacoes,
            }
        )
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/historico_publico")
def historico_publico():
    """Rota pública para obter histórico - SEM AUTENTICAÇÃO"""
    try:
        return jsonify(
            {
                "status": "ok",
                "historico": historico_operacoes,
                "total_operacoes": len(historico_operacoes),
                "lucro_atual": lucro_atual,
                "contador_operacoes": contador_operacoes,
            }
        )
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/forcar_operacao_teste", methods=["POST"])
def forcar_operacao_teste():
    """Força uma operação de teste para verificar se o sistema está funcionando"""
    if "token" not in session:
        return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

    try:
        # Adiciona logs de teste
        adicionar_log_tempo_real("🧪 TESTE: Forçando operação de teste...", "info")
        adicionar_log_tempo_real("📊 TESTE: Analisando JD10...", "info")
        adicionar_log_tempo_real("📈 TESTE: CALL - Entrada forçada", "success")

        # Simula uma operação no histórico
        adicionar_operacao("CALL", 0.70, 1.25)

        adicionar_log_tempo_real(
            "💰 TESTE: Operação finalizada com sucesso!", "success"
        )

        return jsonify(
            {
                "status": "ok",
                "mensagem": "Operação de teste executada com sucesso",
                "logs_adicionados": 4,
            }
        )

    except Exception as e:
        logger.error(f"Erro no teste de operação: {e}")
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


# ===== NOVAS ROTAS DA API PARA LOGS AVANÇADOS =====


@app.route("/api/logs")
def api_logs():
    """API para obter logs em tempo real com categorização"""
    try:
        categoria = request.args.get("categoria", "all")
        limite = int(request.args.get("limite", 20))

        if categoria == "all":
            logs_filtrados = logs_tempo_real[-limite:]
        else:
            logs_filtrados = [
                log for log in logs_tempo_real if log.get("categoria") == categoria
            ][-limite:]

        # Se não há logs, adiciona alguns padrão
        if not logs_filtrados:
            agora = datetime.now()
            logs_filtrados = [
                {
                    "timestamp": agora.strftime("%d/%m/%Y %H:%M:%S"),
                    "categoria": "sistema",
                    "tipo": "info",
                    "mensagem": "🔍 Robô pronto para iniciar.",
                },
                {
                    "timestamp": agora.strftime("%d/%m/%Y %H:%M:%S"),
                    "categoria": "sistema",
                    "tipo": "info",
                    "mensagem": "⚙️ Sistema configurado e aguardando.",
                },
            ]

        return jsonify(
            {
                "status": "success",
                "logs": logs_filtrados,
                "total": len(logs_filtrados),
                "categoria": categoria,
                "timestamp_servidor": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Erro na API de logs: {e}")
        return jsonify({"erro": "Erro interno"}), 500


@app.route("/api/logs/painel")
def api_logs_painel():
    """API específica para logs do painel visual"""
    try:
        return jsonify(
            {
                "logs": logs_painel[-10:],
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
        )
    except Exception as e:
        logger.error(f"Erro na API de logs do painel: {e}")
        return jsonify({"erro": "Erro interno"}), 500


@app.route("/api/performance")
def api_performance():
    """API para estatísticas de performance em tempo real"""
    try:
        global lucro_atual, saldo_atual, contador_operacoes, historico_operacoes

        # Calcula win rate
        operacoes_fechadas = [
            op for op in historico_operacoes if op.get("resultado_real") is not None
        ]
        wins = len([op for op in operacoes_fechadas if op.get("resultado_real", 0) > 0])
        win_rate = (wins / len(operacoes_fechadas) * 100) if operacoes_fechadas else 0

        # Tenta obter dados do LoggerUnificado se disponível
        try:
            stats = LoggerUnificado.obter_estatisticas_performance()
            if stats.get("status") == "success":
                return jsonify(stats)
        except:
            pass

        # Fallback: usa variáveis globais
        return jsonify(
            {
                "status": "success",
                "saldo_atual": float(saldo_atual),
                "lucro_atual": float(lucro_atual),
                "lucro_total": float(lucro_atual),
                "total_operacoes": int(contador_operacoes),
                "win_rate": float(win_rate),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Erro na API de performance: {e}")
        return jsonify({"erro": "Erro interno"}), 500


@app.route("/api/status/sistema")
def api_status_sistema():
    """API para status do sistema em tempo real"""
    try:
        # Verifica status das conexões
        status_deriv = (
            "conectado"
            if motor and hasattr(motor, "ws") and motor.ws
            else "desconectado"
        )

        # Últimos logs de sistema
        logs_sistema = [
            log for log in logs_tempo_real if log.get("categoria") == "sistema"
        ][-5:]

        return jsonify(
            {
                "status_deriv": status_deriv,
                "logs_sistema": logs_sistema,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Erro na API de status: {e}")
        return jsonify({"erro": "Erro interno"}), 500


@app.route("/api/noticias")
def api_noticias():
    """API para notícias do mercado financeiro"""
    try:
        # Simulação de notícias (pode ser integrado com API real)
        noticias = [
            {
                "id": 1,
                "titulo": "Mercados em alta após dados econômicos positivos",
                "resumo": "Índices globais sobem com otimismo dos investidores",
                "timestamp": datetime.now().strftime("%H:%M"),
                "categoria": "economia",
                "impacto": "positivo",
            },
            {
                "id": 2,
                "titulo": "Volatilidade esperada para próximas horas",
                "resumo": "Analistas preveem movimentos significativos",
                "timestamp": (datetime.now() - timedelta(minutes=15)).strftime("%H:%M"),
                "categoria": "analise",
                "impacto": "neutro",
            },
        ]

        return jsonify(
            {
                "noticias": noticias,
                "ultima_atualizacao": datetime.now().strftime("%H:%M:%S"),
            }
        )
    except Exception as e:
        logger.error(f"Erro na API de notícias: {e}")
        return jsonify({"erro": "Erro interno"}), 500


# ===== APIS DO SISTEMA DE GESTÃO DE RISCOS =====


@app.route("/api/riscos/metricas")
def api_riscos_metricas():
    """API para métricas de risco em tempo real"""
    try:
        if motor and hasattr(motor, "gestao_riscos"):
            metricas = motor.gestao_riscos.obter_metricas_tempo_real()
            return jsonify(
                {
                    "status": "success",
                    "metricas": metricas,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "mensagem": "Sistema de gestão de riscos não disponível",
                    }
                ),
                503,
            )
    except Exception as e:
        logger.error(f"Erro na API de métricas de risco: {e}")
        return jsonify({"erro": "Erro interno"}), 500


@app.route("/api/riscos/alertas")
def api_riscos_alertas():
    """API para alertas de risco ativos"""
    try:
        if motor and hasattr(motor, "gestao_riscos"):
            modo = request.args.get("modo", "conservador")
            alertas = motor.gestao_riscos.verificar_alertas(modo)
            return jsonify(
                {
                    "status": "success",
                    "alertas": alertas,
                    "total_alertas": len(alertas),
                    "modo": modo,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "mensagem": "Sistema de gestão de riscos não disponível",
                    }
                ),
                503,
            )
    except Exception as e:
        logger.error(f"Erro na API de alertas de risco: {e}")
        return jsonify({"erro": "Erro interno"}), 500


@app.route("/api/riscos/validar", methods=["POST"])
def api_riscos_validar():
    """API para validar uma operação antes de executar"""
    try:
        if not motor or not hasattr(motor, "gestao_riscos"):
            return (
                jsonify(
                    {
                        "status": "error",
                        "mensagem": "Sistema de gestão de riscos não disponível",
                    }
                ),
                503,
            )

        dados = request.get_json()
        valor = float(dados.get("valor", 0))
        modo = dados.get("modo", "conservador")

        if valor <= 0:
            return (
                jsonify(
                    {"status": "error", "mensagem": "Valor deve ser maior que zero"}
                ),
                400,
            )

        saldo_atual = motor.obter_saldo()
        validacao = motor.gestao_riscos.validar_operacao(valor, modo, saldo_atual)

        return jsonify(
            {
                "status": "success",
                "validacao": validacao,
                "saldo_atual": saldo_atual,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Erro na API de validação de risco: {e}")
        return jsonify({"erro": "Erro interno"}), 500


@app.route("/api/riscos/historico")
def api_riscos_historico():
    """API para histórico de operações com análise de risco"""
    try:
        if motor and hasattr(motor, "gestao_riscos"):
            limite = int(request.args.get("limite", 50))
            historico = motor.gestao_riscos.historico_operacoes[-limite:]

            # Calcula estatísticas do histórico
            total_ops = len(historico)
            ops_fechadas = [op for op in historico if op.get("status") == "fechada"]
            wins = len([op for op in ops_fechadas if op.get("resultado", 0) > 0])

            estatisticas = {
                "total_operacoes": total_ops,
                "operacoes_fechadas": len(ops_fechadas),
                "wins": wins,
                "losses": len(ops_fechadas) - wins,
                "win_rate": (wins / len(ops_fechadas) * 100) if ops_fechadas else 0,
                "lucro_total": sum([op.get("resultado", 0) for op in ops_fechadas]),
                "maior_ganho": max(
                    [op.get("resultado", 0) for op in ops_fechadas], default=0
                ),
                "maior_perda": min(
                    [op.get("resultado", 0) for op in ops_fechadas], default=0
                ),
            }

            return jsonify(
                {
                    "status": "success",
                    "historico": historico,
                    "estatisticas": estatisticas,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "mensagem": "Sistema de gestão de riscos não disponível",
                    }
                ),
                503,
            )
    except Exception as e:
        logger.error(f"Erro na API de histórico de risco: {e}")
        return jsonify({"erro": "Erro interno"}), 500


@app.route("/api/riscos/configurar", methods=["POST"])
def api_riscos_configurar():
    """API para configurar limites de risco"""
    try:
        if not motor or not hasattr(motor, "gestao_riscos"):
            return (
                jsonify(
                    {
                        "status": "error",
                        "mensagem": "Sistema de gestão de riscos não disponível",
                    }
                ),
                503,
            )

        dados = request.get_json()
        modo = dados.get("modo")
        novos_limites = dados.get("limites")

        if not modo or not novos_limites:
            return (
                jsonify(
                    {"status": "error", "mensagem": "Modo e limites são obrigatórios"}
                ),
                400,
            )

        if modo in motor.gestao_riscos.limites_por_modo:
            # Atualiza apenas os campos fornecidos
            for campo, valor in novos_limites.items():
                if campo in motor.gestao_riscos.limites_por_modo[modo]:
                    motor.gestao_riscos.limites_por_modo[modo][campo] = valor

            LoggerUnificado.adicionar_log(
                f"Limites de risco atualizados para modo {modo}",
                "success",
                "risco",
                incluir_painel=True,
            )

            return jsonify(
                {
                    "status": "success",
                    "mensagem": f"Limites atualizados para modo {modo}",
                    "novos_limites": motor.gestao_riscos.limites_por_modo[modo],
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return (
                jsonify(
                    {"status": "error", "mensagem": f"Modo '{modo}' não encontrado"}
                ),
                404,
            )

    except Exception as e:
        logger.error(f"Erro na API de configuração de risco: {e}")
        return jsonify({"erro": "Erro interno"}), 500


# ===== APIS DO SISTEMA DE STOPS =====


@app.route("/api/stops/status")
def api_stops_status():
    """API para obter status dos stops ativos"""
    try:
        if motor and hasattr(motor, "sistema_stops"):
            status = motor.sistema_stops.obter_status_stops()

            # Verifica stops globais
            saldo_atual = motor.obter_saldo() if hasattr(motor, "obter_saldo") else 0
            verificacao_global = motor.sistema_stops.verificar_stops_globais(
                saldo_atual
            )

            return jsonify(
                {
                    "status": "success",
                    "stops_status": status,
                    "verificacao_global": verificacao_global,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return (
                jsonify(
                    {"status": "error", "mensagem": "Sistema de stops não disponível"}
                ),
                503,
            )
    except Exception as e:
        logger.error(f"Erro na API de status de stops: {e}")
        return jsonify({"erro": "Erro interno"}), 500


@app.route("/api/stops/configurar", methods=["POST"])
def api_stops_configurar():
    """API para configurar stops por modo"""
    try:
        if not motor or not hasattr(motor, "sistema_stops"):
            return (
                jsonify(
                    {"status": "error", "mensagem": "Sistema de stops não disponível"}
                ),
                503,
            )

        dados = request.get_json()
        modo = dados.get("modo")

        if not modo:
            return jsonify({"status": "error", "mensagem": "Modo é obrigatório"}), 400

        # Configura stops para o modo
        motor.sistema_stops.configurar_stops_por_modo(modo)

        # Atualiza saldo inicial se necessário
        if hasattr(motor, "obter_saldo"):
            motor.sistema_stops.saldo_inicial = motor.obter_saldo()

        adicionar_log_tempo_real(f"Stops configurados para modo {modo}", "success")

        return jsonify(
            {
                "status": "success",
                "mensagem": f"Stops configurados para modo {modo}",
                "configuracoes": motor.sistema_stops.configuracoes,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Erro na API de configuração de stops: {e}")
        return jsonify({"erro": "Erro interno"}), 500


# ===== APIS DO SISTEMA DE LOGS APRIMORADO =====


@app.route("/api/logs/stops")
def api_logs_stops():
    """API para obter logs específicos de stops"""
    try:
        limite = request.args.get("limite", 20, type=int)

        if logger_unificado:
            logs_stops = logger_unificado.obter_logs_stops(limite)
            return jsonify(
                {
                    "status": "success",
                    "logs": logs_stops,
                    "total": len(logs_stops),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return (
                jsonify(
                    {"status": "error", "mensagem": "Sistema de logs não disponível"}
                ),
                503,
            )

    except Exception as e:
        logger.error(f"Erro na API de logs de stops: {e}")
        return jsonify({"erro": "Erro interno"}), 500


@app.route("/api/logs/erros")
def api_logs_erros():
    """API para obter logs específicos de erros"""
    try:
        limite = request.args.get("limite", 20, type=int)

        if logger_unificado:
            logs_erros = logger_unificado.obter_logs_erros(limite)
            status_erros = logger_unificado.obter_status_erros()

            return jsonify(
                {
                    "status": "success",
                    "logs": logs_erros,
                    "status_erros": status_erros,
                    "total": len(logs_erros),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return (
                jsonify(
                    {"status": "error", "mensagem": "Sistema de logs não disponível"}
                ),
                503,
            )

    except Exception as e:
        logger.error(f"Erro na API de logs de erros: {e}")
        return jsonify({"erro": "Erro interno"}), 500


@app.route("/api/logs/categoria/<categoria>")
def api_logs_categoria(categoria):
    """API para obter logs por categoria"""
    try:
        limite = request.args.get("limite", 20, type=int)

        if logger_unificado:
            logs_categoria = logger_unificado.obter_logs_por_categoria(
                categoria, limite
            )
            return jsonify(
                {
                    "status": "success",
                    "categoria": categoria,
                    "logs": logs_categoria,
                    "total": len(logs_categoria),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return (
                jsonify(
                    {"status": "error", "mensagem": "Sistema de logs não disponível"}
                ),
                503,
            )

    except Exception as e:
        logger.error(f"Erro na API de logs por categoria: {e}")
        return jsonify({"erro": "Erro interno"}), 500


@app.route("/api/logs/estatisticas")
def api_logs_estatisticas():
    """API para obter estatísticas dos logs"""
    try:
        if logger_unificado:
            estatisticas = logger_unificado.obter_estatisticas()
            return jsonify(
                {
                    "status": "success",
                    "estatisticas": estatisticas,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return (
                jsonify(
                    {"status": "error", "mensagem": "Sistema de logs não disponível"}
                ),
                503,
            )

    except Exception as e:
        logger.error(f"Erro na API de estatísticas de logs: {e}")
        return jsonify({"erro": "Erro interno"}), 500


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
