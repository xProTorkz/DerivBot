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

# Importações locais - Ajustadas para nova estrutura
# Motor será importado dinamicamente quando necessário
from config.config import Config
from utils.gerador_licencas import (
    carregar_licencas,
    salvar_licencas,
    obter_hwid,
    obter_ip,
)
from utils.gerador_admin import gerador_admin

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("derivbot.log"), logging.StreamHandler()],
)
logger = logging.getLogger("DerivBot")

# Diretório para armazenamento de dados - Ajustado para nova estrutura
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
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

# Inicialização do Flask - Ajustado para nova estrutura
app = Flask(
    __name__,
    template_folder=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"
    ),
    static_folder=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static"
    ),
)
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
status_motor = "desconectado"  # Status global do motor
logs_tempo_real = []

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
# logs_tempo_real já declarado acima na linha 86
logs_painel = []
max_logs = 100
max_logs_painel = 50


class LoggerUnificado:
    """Sistema de logs unificado para evitar duplicações"""

    logs_sistema = []  # Lista estática para logs do sistema

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
            logger.error(f"{prefixo} [ERRO] {mensagem}")
        elif tipo == "warning":
            logger.warning(f"{prefixo} [AVISO] {mensagem}")
        elif tipo == "success":
            logger.info(f"{prefixo} [OK] {mensagem}")
        elif tipo == "trading":
            logger.info(f"{prefixo} [TRADE] {mensagem}")
        else:
            logger.info(f"{prefixo} [INFO] {mensagem}")

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
                mensagem = f"[WIN] {tipo_operacao} | Entrada: ${valor_entrada:.2f} | Lucro: ${resultado:.2f}"
                tipo_log = "success"
            else:
                mensagem = f"[LOSS] {tipo_operacao} | Entrada: ${valor_entrada:.2f} | Perda: ${abs(resultado):.2f}"
                tipo_log = "warning"
        else:
            # Operação iniciada
            mensagem = f"[ENTRADA] {tipo_operacao} | Valor: ${valor_entrada:.2f} | Ativo: {ativo}"
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
            mensagem = "[CONECTADO] Sistema conectado e operacional"
            tipo_log = "success"
        elif status == "desconectado":
            mensagem = "[DESCONECTADO] Sistema desconectado"
            tipo_log = "error"
        elif status == "reconectando":
            mensagem = "[RECONECTANDO] Tentando reconectar..."
            tipo_log = "warning"
        else:
            mensagem = f"[STATUS] {status}"
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

    @staticmethod
    def obter_logs_recentes(limite=15):
        """Obtém os logs mais recentes"""
        try:
            global logs_tempo_real

            # Retorna os últimos logs da lista global
            logs_recentes = logs_tempo_real[-limite:] if logs_tempo_real else []

            # Formata os logs para a interface
            logs_formatados = []
            for log in logs_recentes:
                logs_formatados.append(
                    {
                        "timestamp": log.get("timestamp", ""),
                        "mensagem": log.get("mensagem", ""),
                        "tipo": log.get("tipo", "info"),
                        "categoria": log.get("categoria", "sistema"),
                    }
                )

            # Se não há logs, adiciona log padrão
            if not logs_formatados:
                logs_formatados = [
                    {
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "mensagem": "Sistema iniciado - Aguardando operações",
                        "tipo": "info",
                        "categoria": "sistema",
                    }
                ]

            return logs_formatados
        except Exception as e:
            logger.error(f"Erro ao obter logs recentes: {e}")
            return [
                {
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "mensagem": "Sistema iniciado",
                    "tipo": "info",
                    "categoria": "sistema",
                }
            ]


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
            f"[LIMITE] Limite de {max_ops} operações simultâneas atingido", "warning"
        )
        return False

    # Verifica intervalo entre operações
    intervalo = intervalo_entre_operacoes.get(modo_atual, 5)
    if agora - ultima_operacao_tempo < intervalo:
        tempo_restante = int(intervalo - (agora - ultima_operacao_tempo))
        adicionar_log_painel(
            f"[AGUARDANDO] Aguardando {tempo_restante}s para próxima operação", "info"
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
        f"[OPERACAO] Nova operação iniciada ({len(operacoes_ativas)} ativas)", "success"
    )


# Sistema de autenticação baseado apenas em licencas.json
# Não criamos mais tokens.json - tudo é gerenciado via licenças


def carregar_licencas():
    """Carrega o arquivo de licenças ou retorna dicionário vazio se não existir."""
    try:
        if os.path.exists(LICENCAS_FILE):
            with open(LICENCAS_FILE, "r", encoding="utf-8") as f:
                licencas = json.load(f)
                logger.info(f"Licenças carregadas: {list(licencas.keys())}")
                return licencas
        else:
            logger.info("Arquivo de licenças não encontrado")
            return {}
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar JSON do arquivo de licenças: {e}")
        return {}
    except Exception as e:
        logger.error(f"Erro ao carregar licenças: {e}")
        return {}


def salvar_licencas(licencas):
    """Salva as licenças no arquivo JSON."""
    try:
        with open(LICENCAS_FILE, "w", encoding="utf-8") as f:
            json.dump(licencas, f, indent=2, ensure_ascii=False)
        logger.info("Licenças salvas com sucesso")
    except Exception as e:
        logger.error(f"Erro ao salvar licenças: {e}")


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

        # Se não encontrou nas licenças, tenta validar diretamente com a API
        if not conta_id:
            # Tenta conectar diretamente com o token para validar
            try:
                # Cria uma instância temporária do motor para validar o token
                from core.motor import Motor

                motor_temp = Motor()
                if motor_temp.conectar(token):
                    # Aguarda um pouco para garantir que a autorização foi processada
                    import time

                    time.sleep(3)  # Aumentei para 3 segundos

                    # Usa a nova função para obter o ID da conta
                    conta_id = motor_temp.obter_id_conta()
                    if conta_id:
                        logger.info(f"[OK] ID da conta obtido da API: {conta_id}")
                        saldo = motor_temp.obter_saldo()
                        logger.info(f"[OK] Saldo obtido da API: {saldo}")
                    else:
                        conta_id = f"account_{token[:8]}"  # Fallback
                        logger.warning("[AVISO] ID da conta não obtido da API")
                        saldo = 0.0

                    tipo_conta = "real" if not token.startswith("demo") else "demo"
                    if not saldo:
                        saldo = 0.0
                    motor_temp.desconectar()
                else:
                    return False, "Token inválido ou sem permissões adequadas"
            except Exception as e:
                logger.error(f"Erro ao validar token diretamente: {e}")
                return False, "Token inválido"

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
    global motor, saldo_atual, status_motor
    # SEMPRE cria o motor, mesmo se der erro
    motor = None
    status_motor = "conectando"
    try:
        from core.motor import Motor

        motor = Motor()
        if token:
            conectado = motor.conectar(token)
            if conectado:
                status_motor = "conectado"
                logger.info("[MOTOR] CONECTADO COM SUCESSO")

                # Tenta obter saldo inicial
                try:
                    import time

                    time.sleep(2)  # Aguarda conexão estabilizar
                    saldo_inicial = motor.obter_saldo()
                    if saldo_inicial:
                        saldo_atual = saldo_inicial
                        logger.info(f"[MOTOR] Saldo inicial obtido: {saldo_inicial}")
                    else:
                        logger.warning("[MOTOR] Não foi possível obter saldo inicial")
                except Exception as e:
                    logger.error(f"Erro ao obter saldo inicial: {e}")

                logger.info("[MOTOR] TURBO INICIALIZADO COM SUCESSO")
                return True
            else:
                status_motor = "erro"
                logger.error("[MOTOR] Falha ao conectar motor com token")
                return False
        else:
            status_motor = "erro"
            logger.warning("[MOTOR] Token não fornecido para inicializar motor")
            return False
    except Exception as motor_error:
        status_motor = "erro"
        logger.error(f"[MOTOR] Erro ao inicializar motor: {motor_error}")
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

        logger.info(f"[DEBUG] Verificando {len(licencas)} licenças encontradas")

        for _, licenca in licencas.items():
            logger.info(f"[DEBUG] Analisando licença: {licenca.get('codigo_licenca')}")

            # Verifica se a licença está ativa
            status = licenca.get("status")
            logger.info(f"[STATUS] Status da licença: {status}")
            if status != "ativa":
                logger.info(f"[ERRO] Licença não está ativa (status: {status})")
                continue

            # Verifica se a licença não expirou
            validade = licenca.get("validade")
            logger.info(f"[DATA] Validade da licença: {validade}")
            if validade != "VITALICIO" and validade != "VITALÍCIO":
                try:
                    data_validade = datetime.strptime(validade, "%Y-%m-%d")
                    if datetime.now() > data_validade:
                        logger.info(f"[ERRO] Licença expirada: {validade}")
                        continue
                    else:
                        logger.info(f"[OK] Licença válida até: {validade}")
                except Exception as e:
                    logger.info(f"[ERRO] Erro ao verificar validade: {e}")
                    continue
            else:
                logger.info(f"[OK] Licença vitalícia")

            # Conta quantos fatores conferem
            fatores_conferidos = 0

            # Fator 1: HWID
            if hwid_atual and hwid_atual == licenca.get("hwid"):
                fatores_conferidos += 1
                logger.info("[OK] HWID confere")
            else:
                logger.info(
                    f"[ERRO] HWID não confere - Atual: {hwid_atual}, Licença: {licenca.get('hwid')}"
                )

            # Fator 2: IP
            if ip_atual and ip_atual == licenca.get("ip"):
                fatores_conferidos += 1
                logger.info("[OK] IP confere")
            else:
                logger.info(
                    f"[ERRO] IP não confere - Atual: {ip_atual}, Licença: {licenca.get('ip')}"
                )

            # Fator 3: Licença ativa (sempre confere se chegou até aqui)
            fatores_conferidos += 1
            logger.info("[OK] Licença ativa confere")

            logger.info(f"[DEBUG] Total de fatores conferidos: {fatores_conferidos}/3")

            # Se pelo menos 2 dos 3 fatores conferem, permite login automático
            if fatores_conferidos >= 2:
                logger.info(
                    f"[SUCESSO] Autenticação automática aprovada para licença {licenca.get('codigo_licenca')}"
                )
                return licenca
            else:
                logger.info(
                    f"[ERRO] Fatores insuficientes ({fatores_conferidos}/3) para licença {licenca.get('codigo_licenca')}"
                )

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
    """[AI] FUNÇÃO ESPECIAL: Força uso de demo quando EU (AI) estiver testando

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
            # [PROTECAO] SEMPRE DEMO PARA TESTES DA AI - PROTEGE SEU DINHEIRO!
            if token_demo:
                logger.info(
                    "[AI] AI TESTANDO: Usando conta DEMO para proteger seu dinheiro!"
                )
                return token_demo, "demo"
            else:
                logger.warning("[AVISO] AI TESTANDO: Sem token demo disponível!")
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
    status_texto = "[LUCRO]" if resultado > 0 else "[PERDA]"

    adicionar_log_painel(
        f"{status_texto} {tipo} finalizada: {resultado_texto} | Total: ${lucro_atual:.2f}",
        "success" if resultado > 0 else "error",
    )

    # Log para tempo real também
    adicionar_log_tempo_real(
        f"[TRADE] {tipo} finalizada: {resultado_texto} (Total: ${lucro_atual:.2f})",
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

    # Tenta login automático com verificação 2/3 fatores
    logger.info("Verificando possibilidade de login automático...")
    licenca_auto = verificar_autenticacao_automatica()

    if licenca_auto:
        logger.info(
            f"[SUCESSO] Login automático aprovado para licença {licenca_auto.get('codigo_licenca')}"
        )

        # Obtém tokens da licença
        token_real, token_demo = obter_tokens_da_licenca(licenca_auto)

        if token_real:
            # Configura sessão automaticamente
            session["token"] = token_real
            session["tipo_conta"] = "real"
            session["codigo_licenca"] = licenca_auto["codigo_licenca"]
            session["deriv_account"] = licenca_auto.get(
                "deriv_real", f"account_{token_real[:8]}"
            )
            session["token_real"] = token_real
            session["token_demo"] = token_demo
            session["saldo"] = 0

            # Inicializa a API
            inicializar_api(token_real)

            logger.info(
                f"[OK] Login automático realizado com sucesso - Licença: {licenca_auto['codigo_licenca']}"
            )
            return redirect(url_for("painel"))
        else:
            logger.warning("[AVISO] Licença encontrada mas tokens não disponíveis")

    # Se não conseguiu login automático, mostra tela de login
    logger.info("Login automático não disponível - redirecionando para login manual")
    return render_template("login.html")


def validar_codigo_licenca(codigo_licenca):
    """Valida se o código de licença é válido (formato correto)"""
    if not codigo_licenca:
        return False

    # Formato esperado: DERIVBOT-XXXX-XXXX (exemplo)
    # Por enquanto, aceita qualquer código não vazio
    # Aqui você pode implementar validação mais específica
    return len(codigo_licenca.strip()) >= 8


def obter_conta_id_do_token(token):
    """Obtém o ID da conta a partir do token da Deriv - versão simplificada para primeiro login"""
    try:
        # Para primeiro login, retorna dados básicos que serão atualizados depois
        # Isso permite que o usuário faça login e vincule a licença

        # Determina tipo baseado no padrão do token (se possível)
        account_type = "real"  # Assume real por padrão

        return {
            "account_id": f"temp_{token[:8]}",  # ID temporário baseado no token
            "account_type": account_type,
            "currency": "USD",
            "balance": 0,
        }
    except Exception as e:
        logger.error(f"Erro ao obter ID da conta: {e}")
        return None


@app.route("/login", methods=["GET", "POST"])
def login():
    """Rota de login com validação de licença"""
    if request.method == "GET":
        # Limpa a sessão e mostra tela de login
        session.clear()
        return render_template("login.html")

    token_real = request.form.get("token_deriv_real", "").strip()
    token_demo = request.form.get("token_deriv_demo", "").strip()
    codigo_licenca = request.form.get("codigo_licenca", "").strip()

    logger.info(
        f"[LOGIN] TENTATIVA DE LOGIN - Código: {codigo_licenca}, Token: {token_real[:10]}..."
    )

    # Verifica se o código de licença foi fornecido
    if not codigo_licenca:
        return render_template("login.html", erro="Código de licença é obrigatório")

    # Verifica se o token real foi fornecido (obrigatório)
    if not token_real:
        return render_template("login.html", erro="Token da conta REAL é obrigatório")

    # Valida o formato do código de licença
    if not validar_codigo_licenca(codigo_licenca):
        return render_template("login.html", erro="Código de licença inválido")

    # Validação básica do formato do token
    if len(token_real) < 10:
        return render_template(
            "login.html", erro="Token real deve ter pelo menos 10 caracteres"
        )

    # Carrega licenças existentes
    licencas = carregar_licencas()
    logger.info(f"[DEBUG] DEBUG: Licenças carregadas: {list(licencas.keys())}")
    logger.info(f"[DEBUG] DEBUG: Procurando código: '{codigo_licenca}'")

    licenca = None
    licenca_key = None

    # Procura licença existente pelo código
    for key, l in licencas.items():
        codigo_na_licenca = l.get("codigo_licenca")
        logger.info(
            f"[DEBUG] DEBUG: Comparando '{codigo_licenca}' com '{codigo_na_licenca}'"
        )
        if codigo_na_licenca == codigo_licenca:
            licenca = l
            licenca_key = key
            logger.info(f"[OK] Licença existente encontrada: {codigo_licenca}")
            break

    if not licenca:
        logger.error(
            f"[ERRO] DEBUG: Licença '{codigo_licenca}' não encontrada nas licenças: {list(licencas.keys())}"
        )
        return render_template(
            "login.html", erro=f"Código de licença '{codigo_licenca}' não encontrado"
        )

    # Licença existe - atualiza dados
    logger.info(f"Licença encontrada: {codigo_licenca}")

    hwid_atual = obter_hwid()
    ip_atual = obter_ip()

    # Atualiza HWID e IP se estiverem vazios (primeiro acesso)
    if not licenca.get("hwid"):
        licenca["hwid"] = hwid_atual
        logger.info(f"HWID vinculado: {hwid_atual}")

    if not licenca.get("ip"):
        licenca["ip"] = ip_atual
        logger.info(f"IP vinculado: {ip_atual}")

    # Atualiza tokens (usuário pode trocar tokens livremente)
    licenca["token_deriv_real"] = token_real
    if token_demo:
        licenca["token_deriv_demo"] = token_demo

    # Obtém o ID da conta real usando uma abordagem mais robusta
    try:
        logger.info(
            f"[DEBUG] Tentando obter ID da conta real para token: {token_real[:10]}..."
        )

        # Usa a função verificar_token que já funciona
        valido, resultado = verificar_token(token_real)
        if valido and resultado:
            conta_id = resultado.get("conta_id", "")
            if (
                conta_id and conta_id != f"account_{token_real[:8]}"
            ):  # Verifica se não é ID temporário
                licenca["deriv_real"] = conta_id
                logger.info(f"[OK] ID da conta real obtido e salvo: {conta_id}")

                # Atualiza saldo se disponível
                saldo = resultado.get("saldo", 0)
                if saldo:
                    logger.info(f"[OK] Saldo da conta: {saldo}")
            else:
                # Se não conseguiu obter ID real, força uma nova tentativa
                logger.warning(
                    "[AVISO] ID da conta não obtido ou é temporário, tentando novamente..."
                )

                # Tenta conectar diretamente para forçar obtenção do ID
                from core.motor import Motor

                motor_temp = Motor()
                if motor_temp.conectar(token_real):
                    import time

                    time.sleep(5)  # Aguarda mais tempo

                    # Primeiro tenta o método normal
                    conta_id_real = motor_temp.obter_id_conta()
                    if not conta_id_real:
                        # Se não funcionou, força uma nova requisição
                        logger.info(
                            "[RECONECTANDO] Tentando método forçado para obter ID real..."
                        )
                        conta_id_real = motor_temp.obter_id_conta_forcado()

                    if conta_id_real:
                        licenca["deriv_real"] = conta_id_real
                        logger.info(
                            f"[OK] ID da conta real obtido na segunda tentativa: {conta_id_real}"
                        )

                        # Obtém e salva o saldo da conta real
                        try:
                            saldo_real = motor_temp.obter_saldo()
                            if saldo_real:
                                licenca["saldo_real"] = saldo_real
                                logger.info(f"[SALDO] Saldo real salvo: {saldo_real}")
                        except Exception as e:
                            logger.error(f"Erro ao obter saldo real: {e}")
                    else:
                        logger.error(
                            "[ERRO] Não foi possível obter ID real da conta mesmo com método forçado"
                        )

                    motor_temp.desconectar()
                else:
                    logger.error(
                        "[ERRO] Não foi possível conectar para obter ID da conta"
                    )
        else:
            logger.warning(f"[AVISO] Não foi possível validar o token: {resultado}")
    except Exception as e:
        logger.error(f"[ERRO] Erro ao obter ID da conta real: {e}")

    # Obtém o ID da conta demo se token demo foi fornecido
    if token_demo:
        try:
            logger.info(
                f"[DEBUG] Tentando obter ID da conta demo para token: {token_demo[:10]}..."
            )

            # Tenta conectar diretamente para obter o ID da conta demo
            from core.motor import Motor

            motor_temp = Motor()
            if motor_temp.conectar(token_demo):
                import time

                time.sleep(3)  # Aguarda conexão

                # Primeiro tenta o método normal
                conta_id_demo = motor_temp.obter_id_conta()
                if not conta_id_demo:
                    # Se não funcionou, força uma nova requisição
                    logger.info(
                        "[RECONECTANDO] Tentando método forçado para obter ID demo..."
                    )
                    conta_id_demo = motor_temp.obter_id_conta_forcado()

                if conta_id_demo:
                    licenca["deriv_demo"] = conta_id_demo
                    logger.info(
                        f"[OK] ID da conta demo obtido e salvo: {conta_id_demo}"
                    )

                    # Obtém e salva o saldo da conta demo
                    try:
                        saldo_demo = motor_temp.obter_saldo()
                        if saldo_demo:
                            licenca["saldo_demo"] = saldo_demo
                            logger.info(f"[SALDO] Saldo demo salvo: {saldo_demo}")
                    except Exception as e:
                        logger.error(f"Erro ao obter saldo demo: {e}")
                else:
                    logger.error("[ERRO] Não foi possível obter ID da conta demo")

                motor_temp.desconectar()
            else:
                logger.error(
                    "[ERRO] Não foi possível conectar para obter ID da conta demo"
                )
        except Exception as e:
            logger.error(f"[ERRO] Erro ao obter ID da conta demo: {e}")

    # Atualiza data de último acesso
    licenca["ultimo_acesso"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Salva alterações
    licencas[licenca_key] = licenca
    salvar_licencas(licencas)

    logger.info(f"Licença atualizada: {codigo_licenca}")

    # Marca a sessão como permanente
    session.permanent = True

    # Salva informações na sessão
    session["codigo_licenca"] = codigo_licenca
    session["token"] = token_real  # Sempre usa token real como principal
    session["tipo_conta"] = "real"  # Sempre inicia com conta real
    session["token_real"] = token_real
    session["token_demo"] = token_demo if token_demo else ""

    # Usa o ID da conta real da licença se disponível
    if licenca.get("deriv_real"):
        session["deriv_account"] = licenca["deriv_real"]
        logger.info(f"[OK] Usando conta real: {licenca['deriv_real']}")
    else:
        session["deriv_account"] = f"account_{token_real[:8]}"  # ID temporário
        logger.warning("[AVISO] Usando ID temporário - conta real não identificada")

    session["saldo"] = 0

    # Inicializa a API com o token real
    inicializar_api(token_real)

    logger.info(f"Login realizado com sucesso - Licença: {codigo_licenca}")

    # Redireciona para o painel
    return redirect(url_for("painel"))


@app.route("/painel")
def painel():
    """Rota do painel"""
    # Verifica autenticação e redireciona se necessário
    redirect_response = redirecionar_se_nao_autenticado()
    if redirect_response:
        return redirect_response

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
    tipo_conta = session.get("tipo_conta", "real")  # Sempre real por padrão
    saldo = session.get("saldo", 0)

    # Debug: Verifica tokens na sessão
    token_real = session.get("token_real", "")
    token_demo = session.get("token_demo", "")
    logger.info(
        f"[DEBUG] Token Real: {'OK' if token_real else 'VAZIO'} | Token Demo: {'OK' if token_demo else 'VAZIO'}"
    )
    logger.info(f"[DEBUG] Tipo Conta: {tipo_conta} | Licença: {codigo_licenca}")

    # Informações da licença
    if licenca:
        codigo_licenca = licenca.get("codigo_licenca", "N/A")
        plano = licenca.get("plano", "vitalicio")  # Usa o plano real da licença
        validade = licenca.get(
            "validade", "VITALICIO"
        )  # Usa a validade real da licença
        logger.info(
            f"[OK] Licença encontrada no painel: {codigo_licenca} - Plano: {plano} - Validade: {validade}"
        )
    else:
        # Se não encontrou a licença, há um problema - redireciona para login
        logger.error(
            f"[ERRO] Licença não encontrada no painel para código: {session.get('codigo_licenca')}"
        )
        session.clear()
        return redirect(url_for("index"))

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


@app.route("/admin")
def admin():
    """Rota do painel administrativo - ACESSO TEMPORARIAMENTE LIBERADO"""
    # TEMPORÁRIO: Liberando acesso para configuração inicial
    logger.info("[ADMIN] Acesso temporário ao admin liberado para configuração")
    return render_template("admin.html")


# === ROTAS DA API ADMIN ===


def verificar_autenticacao():
    """Verifica se o usuário está autenticado"""
    return "token" in session and session.get("codigo_licenca")


def redirecionar_se_nao_autenticado():
    """Redireciona para login se não estiver autenticado"""
    if not verificar_autenticacao():
        logger.warning("Usuário não autenticado - redirecionando para login")
        return redirect(url_for("index"))
    return None


def verificar_acesso_admin():
    """Função auxiliar para verificar acesso admin"""
    # Verificar se está logado
    if not verificar_autenticacao():
        return False, "Não autenticado"

    # Verificar licença autorizada
    codigo_licenca = session.get("codigo_licenca")
    LICENCAS_ADMIN_AUTORIZADAS = ["DERIVBOT-82YM-E0VX"]

    if codigo_licenca not in LICENCAS_ADMIN_AUTORIZADAS:
        logger.warning(
            f"Tentativa de acesso API admin não autorizado - Licença: {codigo_licenca}"
        )
        return False, "Acesso negado"

    return True, "Autorizado"


@app.route("/api/admin/stats")
def admin_stats():
    """API para estatísticas do dashboard"""
    # Verificar acesso admin
    autorizado, mensagem = verificar_acesso_admin()
    if not autorizado:
        return jsonify({"success": False, "message": mensagem}), 403

    try:
        stats = gerador_admin.get_license_stats()
        recentes = gerador_admin.get_recent_licenses(5)

        return jsonify({"success": True, "stats": stats, "recentes": recentes})
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin/generate-license", methods=["POST"])
def admin_generate_license():
    """API para gerar nova licença"""
    # Verificar acesso admin
    autorizado, mensagem = verificar_acesso_admin()
    if not autorizado:
        return jsonify({"success": False, "message": mensagem}), 403

    try:
        data = request.get_json()

        # Validar dados obrigatórios
        tipo = data.get("tipo", "vitalicio")
        email = data.get("email", "")
        nome = data.get("nome", "")
        observacoes = data.get("observacoes", "")
        enviar_email = data.get("enviar_email", False)

        # Gerar licença (com envio automático de email)
        sucesso, codigo_licenca, mensagem = gerador_admin.create_license(
            tipo=tipo,
            email=email,
            nome=nome,
            observacoes=observacoes,
            enviar_email=enviar_email,
        )

        if not sucesso:
            return jsonify({"success": False, "message": mensagem})

        # Verificar se email foi enviado (informação já está na mensagem)
        email_enviado = "email enviado automaticamente" in mensagem.lower()

        return jsonify(
            {
                "success": True,
                "codigo_licenca": codigo_licenca,
                "message": mensagem,
                "email_enviado": email_enviado,
            }
        )

    except Exception as e:
        logger.error(f"Erro ao gerar licença: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin/licenses")
def admin_licenses():
    """API para listar todas as licenças"""
    # Verificar acesso admin
    autorizado, mensagem = verificar_acesso_admin()
    if not autorizado:
        return jsonify({"success": False, "message": mensagem}), 403

    try:
        licenses = gerador_admin.get_recent_licenses(100)  # Todas as licenças
        return jsonify({"success": True, "licenses": licenses})
    except Exception as e:
        logger.error(f"Erro ao listar licenças: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin/delete-license", methods=["POST"])
def admin_delete_license():
    """API para excluir licença"""
    # Verificar acesso admin
    autorizado, mensagem = verificar_acesso_admin()
    if not autorizado:
        return jsonify({"success": False, "message": mensagem}), 403

    try:
        data = request.get_json()
        codigo_licenca = data.get("codigo_licenca")

        if not codigo_licenca:
            return jsonify(
                {"success": False, "message": "Código da licença é obrigatório"}
            )

        sucesso, mensagem = gerador_admin.delete_license(codigo_licenca)
        return jsonify({"success": sucesso, "message": mensagem})

    except Exception as e:
        logger.error(f"Erro ao excluir licença: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin/send-email", methods=["POST"])
def admin_send_email():
    """API para enviar email manual"""
    # Verificar acesso admin
    autorizado, mensagem = verificar_acesso_admin()
    if not autorizado:
        return jsonify({"success": False, "message": mensagem}), 403

    try:
        data = request.get_json()
        codigo_licenca = data.get("codigo_licenca")
        email = data.get("email")
        nome = data.get("nome", "")

        if not codigo_licenca or not email:
            return jsonify(
                {
                    "success": False,
                    "message": "Código da licença e email são obrigatórios",
                }
            )

        sucesso, mensagem = gerador_admin.send_email(codigo_licenca, email, nome)
        return jsonify({"success": sucesso, "message": mensagem})

    except Exception as e:
        logger.error(f"Erro ao enviar email: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin/resend-email", methods=["POST"])
def admin_resend_email():
    """API para reenviar email de uma licença"""
    # Verificar acesso admin
    autorizado, mensagem = verificar_acesso_admin()
    if not autorizado:
        return jsonify({"success": False, "message": mensagem}), 403

    try:
        data = request.get_json()
        codigo_licenca = data.get("codigo_licenca")

        if not codigo_licenca:
            return jsonify(
                {"success": False, "message": "Código da licença é obrigatório"}
            )

        # Buscar dados da licença
        licencas = gerador_admin.load_licenses()
        licenca = None
        for lic in licencas.values():
            if lic.get("codigo_licenca") == codigo_licenca:
                licenca = lic
                break

        if not licenca:
            return jsonify({"success": False, "message": "Licença não encontrada"})

        email = licenca.get("cliente_email")
        nome = licenca.get("cliente_nome", "")

        if not email:
            return jsonify(
                {
                    "success": False,
                    "message": "Email do cliente não encontrado na licença",
                }
            )

        sucesso, mensagem = gerador_admin.send_email(codigo_licenca, email, nome)
        return jsonify({"success": sucesso, "message": mensagem})

    except Exception as e:
        logger.error(f"Erro ao reenviar email: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin/email-config")
def admin_email_config():
    """API para obter configuração de email"""
    # Verificar acesso admin
    autorizado, mensagem = verificar_acesso_admin()
    if not autorizado:
        return jsonify({"success": False, "message": mensagem}), 403

    try:
        config = gerador_admin.load_config()
        email_config = config.get("email", {})

        # Não retornar senha por segurança
        safe_config = {
            "smtp_server": email_config.get("smtp_server", ""),
            "smtp_port": email_config.get("smtp_port", 587),
            "email_user": email_config.get("email_user", ""),
        }

        return jsonify({"success": True, "config": safe_config})
    except Exception as e:
        logger.error(f"Erro ao obter configuração de email: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin/save-email-config", methods=["POST"])
def admin_save_email_config():
    """API para salvar configuração de email"""
    # Verificar acesso admin
    autorizado, mensagem = verificar_acesso_admin()
    if not autorizado:
        return jsonify({"success": False, "message": mensagem}), 403

    try:
        data = request.get_json()

        smtp_server = data.get("smtp_server", "")
        smtp_port = data.get("smtp_port", 587)
        email_user = data.get("email_user", "")
        email_pass = data.get("email_pass", "")

        sucesso, mensagem = gerador_admin.save_email_config(
            smtp_server, smtp_port, email_user, email_pass
        )

        return jsonify({"success": sucesso, "message": mensagem})

    except Exception as e:
        logger.error(f"Erro ao salvar configuração de email: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin/test-email", methods=["POST"])
def admin_test_email():
    """API para testar configuração de email"""
    # Verificar acesso admin
    autorizado, mensagem = verificar_acesso_admin()
    if not autorizado:
        return jsonify({"success": False, "message": mensagem}), 403

    try:
        data = request.get_json()
        email_destino = data.get("email_destino")

        if not email_destino:
            return jsonify(
                {"success": False, "message": "Email de destino é obrigatório"}
            )

        sucesso, mensagem = gerador_admin.test_email_config(email_destino)
        return jsonify({"success": sucesso, "message": mensagem})

    except Exception as e:
        logger.error(f"Erro ao testar email: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin/email-preview")
def admin_email_preview():
    """API para preview do template de email"""
    # Verificar acesso admin
    autorizado, mensagem = verificar_acesso_admin()
    if not autorizado:
        return jsonify({"success": False, "message": mensagem}), 403

    try:
        template = gerador_admin.get_email_template(
            "DERIVBOT-XXXX-XXXX", "Cliente Exemplo"
        )
        return jsonify({"success": True, "preview": template})
    except Exception as e:
        logger.error(f"Erro ao gerar preview: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin/api-key")
def admin_api_key():
    """API para obter chave API atual"""
    # Verificar acesso admin
    autorizado, mensagem = verificar_acesso_admin()
    if not autorizado:
        return jsonify({"success": False, "message": mensagem}), 403

    try:
        config = gerador_admin.load_config()
        api_key = config.get("api_key", "")

        return jsonify({"success": True, "api_key": api_key})
    except Exception as e:
        logger.error(f"Erro ao obter chave API: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin/generate-api-key", methods=["POST"])
def admin_generate_api_key():
    """API para gerar nova chave API"""
    # Verificar acesso admin
    autorizado, mensagem = verificar_acesso_admin()
    if not autorizado:
        return jsonify({"success": False, "message": mensagem}), 403

    try:
        new_key = gerador_admin.generate_new_api_key()
        return jsonify({"success": True, "api_key": new_key})
    except Exception as e:
        logger.error(f"Erro ao gerar chave API: {e}")
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/admin/export-licenses")
def admin_export_licenses():
    """API para exportar licenças em CSV"""
    # Verificar acesso admin
    autorizado, mensagem = verificar_acesso_admin()
    if not autorizado:
        return jsonify({"success": False, "message": mensagem}), 403

    try:
        import csv
        import io

        licenses = gerador_admin.get_recent_licenses(1000)  # Todas

        # Criar CSV em memória
        output = io.StringIO()
        writer = csv.writer(output)

        # Cabeçalho
        writer.writerow(
            [
                "Código",
                "Tipo",
                "Status",
                "Cliente Nome",
                "Cliente Email",
                "Data Criação",
                "Validade",
                "HWID",
                "IP",
                "Observações",
            ]
        )

        # Dados
        for lic in licenses:
            writer.writerow(
                [
                    lic.get("codigo_licenca", ""),
                    lic.get("plano", ""),
                    lic.get("status", ""),
                    lic.get("cliente_nome", ""),
                    lic.get("cliente_email", ""),
                    lic.get("data_criacao", ""),
                    lic.get("validade", ""),
                    lic.get("hwid", ""),
                    lic.get("ip", ""),
                    lic.get("observacoes", ""),
                ]
            )

        # Preparar resposta
        output.seek(0)

        from flask import make_response

        response = make_response(output.getvalue())
        response.headers["Content-Type"] = "text/csv"
        response.headers["Content-Disposition"] = (
            f'attachment; filename=licencas_derivbot_{datetime.now().strftime("%Y%m%d")}.csv'
        )

        return response

    except Exception as e:
        logger.error(f"Erro ao exportar licenças: {e}")
        return jsonify({"success": False, "message": str(e)})


# === API PÚBLICA PARA INTEGRAÇÃO ===


@app.route("/api/public/generate-license", methods=["POST"])
def public_generate_license():
    """API pública para gerar licença (para integração com sistemas de venda)"""
    try:
        data = request.get_json()

        # Validar chave API
        api_key = data.get("api_key")
        if not api_key or not gerador_admin.validate_api_key(api_key):
            return jsonify({"success": False, "message": "Chave API inválida"}), 401

        # Validar dados obrigatórios
        tipo = data.get("tipo", "vitalicio")
        email = data.get("email")
        nome = data.get("nome", "")
        observacoes = data.get("observacoes", "")
        enviar_email = data.get("enviar_email", True)

        if not email:
            return jsonify({"success": False, "message": "Email é obrigatório"}), 400

        # Gerar licença (com envio automático de email)
        sucesso, codigo_licenca, mensagem = gerador_admin.create_license(
            tipo=tipo,
            email=email,
            nome=nome,
            observacoes=observacoes,
            enviar_email=enviar_email,
        )

        if not sucesso:
            return jsonify({"success": False, "message": mensagem}), 500

        # Verificar se email foi enviado (informação já está na mensagem)
        email_enviado = "email enviado automaticamente" in mensagem.lower()

        logger.info(f"Licença gerada via API: {codigo_licenca} para {email}")

        return jsonify(
            {
                "success": True,
                "codigo_licenca": codigo_licenca,
                "message": mensagem,
                "email_enviado": email_enviado,
            }
        )

    except Exception as e:
        logger.error(f"Erro na API pública: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500


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
            adicionar_log_tempo_real("[ENTRADA] Iniciando Estratégia Turbo...", "info")
            adicionar_log_tempo_real(
                f"[DADOS] Modo: {modo.upper()}, Meta: ${meta:.0f}", "info"
            )

            # Inicia o sistema inteligente no motor - VERSÃO SEGURA
            adicionar_log_tempo_real("[CONFIG] Configurando motor...", "info")
            try:
                # Usa motor existente se disponível e conectado
                if motor and hasattr(motor, "conectado") and motor.conectado:
                    logger.info("Usando motor existente já conectado")
                else:
                    # Cria novo motor apenas se necessário
                    from core.motor import Motor

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
                    adicionar_log_tempo_real(
                        "[INICIANDO] Motor Turbo iniciado!", "success"
                    )
                    adicionar_log_tempo_real(
                        "[ATIVO] Sistema inteligente ATIVO!", "info"
                    )
                else:
                    logger.warning(
                        "Motor não possui método iniciar_sistema_inteligente"
                    )
                    adicionar_log_tempo_real("[AVISO] Motor em modo básico", "warning")

                # Atualiza variável global
                globals()["motor"] = motor

            except Exception as e:
                logger.error(f"ERRO ao iniciar sistema: {e}")
                adicionar_log_tempo_real(f"[ERRO] ERRO: {str(e)}", "error")

                # Continua mesmo com erro para não travar a interface
                adicionar_log_tempo_real(
                    "[RECONECTANDO] Sistema em modo básico", "warning"
                )

            return jsonify(
                {
                    "status": "iniciado",
                    "modo": modo,
                    "meta": meta,
                    "mensagem": f"Robô iniciado no modo {modo.upper()} com sistema inteligente",
                }
            )
    except Exception as e:
        logger.error(f"Erro ao alternar robô: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/api/status/sistema")
def api_status_sistema():
    """Rota para obter status do sistema"""
    try:
        if motor and hasattr(motor, "ws") and motor.ws:
            if motor.ws.connected:
                status_deriv = "conectado"
            else:
                status_deriv = "desconectado"
        else:
            status_deriv = "desconectado"

        return jsonify(
            {
                "status": "success",
                "status_deriv": status_deriv,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Erro ao obter status do sistema: {e}")
        return jsonify(
            {"status": "error", "status_deriv": "desconectado", "error": str(e)}
        )


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

        # Status do motor - USANDO STATUS GLOBAL
        global status_motor

        # Atualiza status_motor baseado no estado real
        # Se há saldo válido e token válido, considera conectado
        if saldo_valor > 0 and "token" in session:
            status_motor = "conectado"
        elif motor and hasattr(motor, "conectado") and motor.conectado:
            status_motor = "conectado"
        elif motor is None:
            status_motor = "desconectado"
        else:
            status_motor = "erro"

        motor_status = {
            "conectado": status_motor == "conectado",
            "operacoes_ativas": 0,
            "status": status_motor,
        }
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
                    "status": status_motor,
                }
            except Exception as e:
                logger.error(f"Erro ao obter status do motor: {e}")
                motor_status = {
                    "conectado": False,
                    "operacoes_ativas": 0,
                    "status": status_motor,
                }

        # Prepara dados seguros para JSON
        # Converte valores de forma segura
        lucro_valor = 0.0
        saldo_valor = 0.0

        try:
            # Se lucro_atual é uma função, chama ela; senão usa o valor
            if callable(lucro_atual):
                lucro_valor = float(lucro_atual())
            elif isinstance(lucro_atual, (int, float)):
                lucro_valor = float(lucro_atual)
        except:
            lucro_valor = 0.0

        try:
            # Se saldo_atual é uma função, chama ela; senão usa o valor
            if callable(saldo_atual):
                saldo_valor = float(saldo_atual())
            elif isinstance(saldo_atual, (int, float)):
                saldo_valor = float(saldo_atual)
        except:
            saldo_valor = 0.0

        # Obtém logs de forma segura
        try:
            global logs_tempo_real
            logs_recentes = logs_tempo_real[-20:] if logs_tempo_real else []
        except Exception as e:
            logger.error(f"Erro ao obter logs tempo real: {e}")
            logs_recentes = []

        response_data = {
            "ativo": bool(robo_ativo),
            "modo": str(modo_operacao or "iniciante"),
            "meta": float(meta_diaria or 20.0),
            "lucro": lucro_valor,
            "saldo": saldo_valor,
            "operacoes": int(contador_operacoes),
            "status_operacao": str(status_operacao or "parado"),
            "mensagem_log": str(ultima_mensagem or "Sistema pronto"),
            "ativo_atual": ativo_info,
            "motor_status": motor_status,
            "logs_tempo_real": logs_recentes,
            "historico_recente": (
                historico_operacoes[-3:] if historico_operacoes else []
            ),
        }

        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Erro ao obter status do robô: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


# ===== ROTAS DE API FALTANTES =====


@app.route("/api/logs")
def api_logs():
    """Rota para obter logs do sistema"""
    try:
        limite = request.args.get("limite", 15, type=int)
        logs = LoggerUnificado.obter_logs_recentes(limite)
        return jsonify({"status": "ok", "logs": logs})
    except Exception as e:
        logger.error(f"Erro ao obter logs: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/logs_tempo_real")
def api_logs_tempo_real():
    """Rota para logs em tempo real"""
    try:
        logs = LoggerUnificado.obter_logs_recentes(10)
        return jsonify({"status": "ok", "logs": logs})
    except Exception as e:
        logger.error(f"Erro ao obter logs tempo real: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/api/performance")
def api_performance():
    """Rota para métricas de performance"""
    try:
        return jsonify(
            {
                "status": "ok",
                "performance": {
                    "win_rate": 0.0,
                    "total_operacoes": 0,
                    "lucro_total": 0.0,
                    "tempo_ativo": "00:00:00",
                },
            }
        )
    except Exception as e:
        logger.error(f"Erro ao obter performance: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/api/riscos/metricas")
def api_riscos_metricas():
    """Rota para métricas de risco"""
    try:
        return jsonify(
            {
                "status": "ok",
                "riscos": {
                    "drawdown_atual": 0.0,
                    "drawdown_maximo": 0.0,
                    "exposicao_atual": 0.0,
                    "limite_diario": 100.0,
                },
            }
        )
    except Exception as e:
        logger.error(f"Erro ao obter métricas de risco: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/api/riscos/alertas")
def api_riscos_alertas():
    """Rota para alertas de risco"""
    try:
        modo = request.args.get("modo", "conservador")
        return jsonify({"status": "ok", "alertas": [], "modo": modo})
    except Exception as e:
        logger.error(f"Erro ao obter alertas de risco: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/historico")
def historico():
    """Rota para histórico de operações"""
    try:
        return jsonify({"status": "ok", "historico": []})
    except Exception as e:
        logger.error(f"Erro ao obter histórico: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/api/noticias")
def api_noticias():
    """Rota para notícias do mercado"""
    try:
        return jsonify({"status": "ok", "noticias": []})
    except Exception as e:
        logger.error(f"Erro ao obter notícias: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/status_deriv")
def status_deriv():
    """Rota para status da Deriv"""
    try:
        return jsonify({"status": "ok", "deriv_status": "online", "latencia": "50ms"})
    except Exception as e:
        logger.error(f"Erro ao obter status Deriv: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/saldo_atual")
def api_saldo_atual():
    """Rota para obter saldo atual da conta"""
    try:
        # Verifica autenticação
        if "token" not in session:
            return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

        saldo = 0.0
        tipo_conta = session.get("tipo_conta", "real")
        token_atual = session.get("token", "")

        logger.info(
            f"[SALDO] Obtendo saldo para conta {tipo_conta} com token {token_atual[:10]}..."
        )

        # Método 1: Obtém saldo do motor se conectado
        if motor and hasattr(motor, "conectado") and motor.conectado:
            try:
                saldo = motor.obter_saldo()
                logger.info(f"[SALDO] Saldo obtido do motor: {saldo} ({tipo_conta})")
            except Exception as e:
                logger.error(f"Erro ao obter saldo do motor: {e}")

        # Método 2: Se não conseguiu obter do motor, tenta obter da licença (cache)
        if saldo == 0.0:
            try:
                licencas = carregar_licencas()
                codigo_licenca = session.get("codigo_licenca")

                for licenca in licencas.values():
                    if licenca.get("codigo_licenca") == codigo_licenca:
                        # Obtém saldo salvo na licença (se houver)
                        saldo_salvo = licenca.get(f"saldo_{tipo_conta}", 0.0)
                        if saldo_salvo:
                            saldo = saldo_salvo
                            logger.info(
                                f"[SALDO] Saldo obtido da licença (cache): {saldo} ({tipo_conta})"
                            )
                        break
            except Exception as e:
                logger.error(f"Erro ao obter saldo da licença: {e}")

        # Atualiza sessão com o saldo obtido
        session["saldo"] = saldo

        return jsonify(
            {
                "status": "ok",
                "saldo": saldo,
                "tipo_conta": tipo_conta,
                "formatado": f"${saldo:.2f}",
            }
        )

    except Exception as e:
        logger.error(f"Erro ao obter saldo atual: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route("/selecionar_conta", methods=["POST"])
def selecionar_conta():
    """Rota para alternar entre conta real e demo"""
    try:
        # Verifica autenticação
        if "token" not in session:
            return jsonify({"status": "erro", "mensagem": "Não autenticado"}), 401

        data = request.get_json()
        # Aceita tanto 'tipo_conta' quanto 'tipo' para compatibilidade
        tipo_conta = data.get("tipo_conta") or data.get("tipo", "real")

        if tipo_conta not in ["real", "demo"]:
            return (
                jsonify({"status": "erro", "mensagem": "Tipo de conta inválido"}),
                400,
            )

        # Obtém tokens da sessão
        token_real = session.get("token_real", "")
        token_demo = session.get("token_demo", "")

        if tipo_conta == "real" and not token_real:
            return (
                jsonify({"status": "erro", "mensagem": "Token real não disponível"}),
                400,
            )

        if tipo_conta == "demo" and not token_demo:
            return (
                jsonify({"status": "erro", "mensagem": "Token demo não disponível"}),
                400,
            )

        # Atualiza sessão
        session["tipo_conta"] = tipo_conta
        token_ativo = token_real if tipo_conta == "real" else token_demo
        session["token"] = token_ativo

        # Obtém ID da conta da licença
        licencas = carregar_licencas()
        codigo_licenca = session.get("codigo_licenca")

        for licenca in licencas.values():
            if licenca.get("codigo_licenca") == codigo_licenca:
                if tipo_conta == "real":
                    session["deriv_account"] = licenca.get(
                        "deriv_real", f"account_{token_real[:8]}"
                    )
                else:
                    session["deriv_account"] = licenca.get(
                        "deriv_demo", f"account_{token_demo[:8]}"
                    )
                break

        # Reinicializa motor com novo token
        if motor:
            try:
                motor.desconectar()
                motor.conectar(token_ativo)
                logger.info(f"[RECONECTANDO] Motor reconectado com conta {tipo_conta}")
            except Exception as e:
                logger.error(f"Erro ao reconectar motor: {e}")

        return jsonify(
            {
                "status": "ok",
                "tipo_conta": tipo_conta,
                "mensagem": f"Conta {tipo_conta} selecionada com sucesso",
            }
        )

    except Exception as e:
        logger.error(f"Erro ao selecionar conta: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


if __name__ == "__main__":
    # Carrega o histórico na inicialização
    carregar_historico()

    # Adiciona logs iniciais para não mostrar "Aguardando"
    adicionar_log_tempo_real("Sistema DerivBot iniciado com sucesso", "success")
    adicionar_log_tempo_real("Aguardando autenticação do usuário", "info")
    adicionar_log_tempo_real("Sistema pronto para operações", "info")

    # Inicia o servidor Flask
    logger.info("[SISTEMA] Iniciando DerivBot...")
    app.run(host="0.0.0.0", port=5000, debug=False)
