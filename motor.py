import time
import websocket
import json
import config
import threading
import os
import sys
import traceback  # Coloca isso no topo do arquivo se ainda não tiver


from logs import registrar_operacao
from config import status_robo, salvar_status, parar_robo, iniciar_robo
from datetime import datetime
from operacoes import comprar_contrato, encerrar_contrato, verificar_lucro
from catalogador import analisar_entrada_chatgpt, analisar_saida_chatgpt

LOGS_PATH = "data/logs.txt"
estado = {
    "robo_ativo": False,
    "modo": None,
    "token": None,
    "meta": 0,
    "tipo_conta": None,
    "lucro_total": 0.0,  # Garantido desde o início
}

contratos_abertos = []  # Lista de contratos abertos monitorados


def conectar_ws():
    return websocket.create_connection(
        "wss://ws.derivws.com/websockets/v3?app_id=71203"
    )


def autenticar(ws, token):
    ws.send(json.dumps({"authorize": token}))
    raw = ws.recv()
    if not raw.strip():
        raise ValueError("Resposta vazia recebida do WebSocket.")
    resposta = json.loads(raw)

    ws.close()

    if "error" in resposta:
        raise Exception("Erro ao autenticar: " + resposta["error"]["message"])


# ================== FUNÇÃO DE CONSULTA ===================
def status_contrato(contract_id, token):
    """Retorna o status completo do contrato, incluindo lucro e status aberto/fechado."""
    try:
        ws = websocket.WebSocket()
        ws.connect("wss://ws.derivws.com/websockets/v3?app_id=71287")

        # Autentica
        ws.send(json.dumps({"authorize": token}))
        auth_raw = ws.recv()
        if not auth_raw.strip():
            raise ValueError("Resposta vazia na autorização do WebSocket.")

        # Solicita status do contrato
        ws.send(json.dumps({"proposal_open_contract": 1, "contract_id": contract_id}))
        raw = ws.recv()

        if not raw.strip():
            raise ValueError("Resposta vazia ao solicitar status do contrato.")

        data = json.loads(raw)

        # Fecha conexão
        ws.close()

        # Verifica erro
        if "error" in data:
            raise Exception("Erro: " + data["error"]["message"])

        contrato = data.get("proposal_open_contract", {})
        status = contrato.get("status", "unknown")

        lucro_raw = contrato.get("profit", 0.0)
        try:
            lucro = float(lucro_raw) if lucro_raw is not None else 0.0
        except:
            lucro = 0.0

        # Log opcional para debug
        print(
            f"[DEBUG CONTRATO] Status={status} | Lucro={lucro} | ID={contract_id} | Pode vender={contrato.get('is_valid_to_sell')}"
        )

        return {
            "status": status,
            "lucro": lucro,
            "contract": contrato,
        }

    except Exception as e:
        print(f"[ERRO] Falha ao obter status do contrato {contract_id}: {e}")
        return {
            "status": "erro",
            "lucro": 0.0,
            "erro": str(e),
            "contract": {},
        }


# === Função para pegar últimos ticks do ativo ===
def obter_ultimos_precos(ativo="1HZ10V", quantidade=20, max_retries=3):
    for attempt in range(max_retries):
        try:
            print(
                f"[DEBUG] Tentativa {attempt+1}/{max_retries} - Solicitando ticks para {ativo}"
            )

            ws = websocket.WebSocket()
            ws.connect("wss://ws.derivws.com/websockets/v3?app_id=71203", timeout=10)

            payload = {
                "ticks_history": ativo,
                "count": quantidade,
                "end": "latest",
                "style": "ticks",
            }

            ws.send(json.dumps(payload))

            # Recebe resposta com timeout
            raw = ws.recv()
            ws.close()

            if not raw or not raw.strip():
                print("[ERRO] Resposta vazia da API")
                continue

            try:
                resposta = json.loads(raw)
            except json.JSONDecodeError as e:
                print(
                    f"[ERRO JSON] Falha ao decodificar: {e} | Resposta: {raw[:200]}..."
                )
                continue

            if "error" in resposta:
                print(f"[ERRO API] {resposta['error']['message']}")
                continue

            if "history" not in resposta or "prices" not in resposta["history"]:
                print(f"[ERRO ESTRUTURA] Resposta inesperada: {resposta}")
                continue

            ticks = resposta["history"]["prices"]
            print(f"[DEBUG] {len(ticks)} ticks recebidos")
            return ticks

        except websocket.WebSocketTimeoutException:
            print("[ERRO] Timeout na conexão WebSocket")
        except Exception as e:
            print(f"[ERRO] Tentativa {attempt+1} falhou: {str(e)}")
        finally:
            try:
                ws.close()
            except:
                pass

        time.sleep(1)  # Espera antes de tentar novamente

    print("[ERRO] Todas as tentativas falharam")
    return []


def consultar_saldo(token):
    try:
        ws = websocket.WebSocket()
        ws.connect("wss://ws.derivws.com/websockets/v3?app_id=71203")

        # Envia autorização e ignora a resposta
        ws.send(json.dumps({"authorize": token}))
        _ = ws.recv()

        # Solicita saldo
        ws.send(json.dumps({"balance": 1, "subscribe": 0}))
        raw = ws.recv()

        # Verifica se veio vazio
        if not raw or not raw.strip():
            raise ValueError("Resposta vazia ou nula ao solicitar saldo.")

        # Tenta parsear o JSON
        try:
            resposta = json.loads(raw)
        except json.JSONDecodeError as e:
            print(
                f"\n[ERRO JSON - SALDO] Falha ao decodificar resposta:\n{e}\nConteúdo bruto:\n{repr(raw[:500])}\n"
            )
            return 0

        ws.close()

        # Valida estrutura esperada
        if "balance" not in resposta or "balance" not in resposta["balance"]:
            print(f"[ERRO ESTRUTURA - SALDO] Resposta inesperada: {resposta}")
            return 0

        return resposta["balance"]["balance"]

    except Exception as e:
        print(f"[ERRO SALDO] {e}")
        return 0


# === MOTOR PRINCIPAL ===
def executar_operacao_sniper(modo, token, meta, tipo_conta):
    """Executa a estratégia de trading sniper com gerenciamento robusto de operações."""

    import threading
    import time
    import traceback

    iniciar_robo()
    contratos_abertos = []
    entradas_recentes = []
    TAKE_IMEDIATO = 0.25

    CONFIG_MODOS = {
        "iniciante": {
            "ativo": "1HZ10V",
            "porcentagem": 0.05,
            "limite": 3,
            "timeout": 30,
            "multiplier": 100,
        },
        "conservador": {
            "ativo": "1HZ50V",
            "porcentagem": 0.10,
            "limite": 5,
            "timeout": 45,
            "multiplier": 200,
        },
        "agressivo": {
            "ativo": "1HZ100V",
            "porcentagem": 0.20,
            "limite": 10,
            "timeout": 60,
            "multiplier": 400,
        },
    }

    config = CONFIG_MODOS.get(modo.lower(), CONFIG_MODOS["iniciante"])
    entrada = max(1.0, round(meta * config["porcentagem"], 2))
    stop_loss = meta / 2
    ativo = config["ativo"]

    print(f"\n🟢 Iniciando bot no modo {modo.upper()}")
    print(f"📊 Configuração: Ativo={ativo} | Entrada=${entrada:.2f}")
    print(f"🎯 Objetivos: Meta=${meta:.2f} | Stop=${stop_loss:.2f}")
    print(f"⚙️ Limites: {config['limite']} operações | Timeout: {config['timeout']}s")

    try:
        threading.Thread(
            target=monitorar_contratos_antigos,
            args=(token, contratos_abertos, entradas_recentes),
            daemon=True,
        ).start()
    except Exception as e:
        print(f"🚨 Falha ao iniciar monitoramento: {str(e)}")
        parar_robo()
        return

    operacoes_ativas = 0
    lucro_total = 0.0
    perdas_total = 0.0
    cooldown = 3

    def operacao_individual():
        nonlocal lucro_total, perdas_total, operacoes_ativas

        def executar():
            try:
                contract_id = comprar_contrato(
                    valor=entrada,
                    token=token,
                    ativo=ativo,
                    multiplier=config["multiplier"],
                )
                print(f"📩 Contrato {contract_id} comprado (${entrada:.2f})")
                contratos_abertos.append(
                    {"id": contract_id, "entrada": time.time(), "valor": entrada}
                )
                time.sleep(10)

                start_time = time.time()
                while time.time() - start_time < config["timeout"]:
                    try:
                        status_info = status_contrato(contract_id, token)
                        if not status_info:
                            time.sleep(1)
                            continue

                        contrato = status_info.get("contract", {})
                        status = contrato.get("status", "desconhecido")
                        is_sellable = contrato.get("is_valid_to_sell", 0)
                        lucro_raw = contrato.get("profit", 0)

                        try:
                            lucro = float(lucro_raw)
                        except:
                            lucro = 0.0

                        if status == "open" and not is_sellable:
                            print(f"[INFO] Contrato ainda não vendável... aguardando.")
                            time.sleep(1)
                            continue

                        if status != "open":
                            resultado = "lucro" if lucro > 0 else "prejuízo"
                            entradas_recentes.append(resultado)
                            registrar_operacao(resultado, lucro, modo, entrada)
                            print(f"🔚 Contrato {contract_id} fechado: ${lucro:.2f}")
                            if lucro > 0:
                                lucro_total += lucro
                            else:
                                perdas_total += abs(lucro)
                            return

                        if lucro <= -entrada * 0.3 and is_sellable:
                            encerrar_contrato(contract_id, token)
                            registrar_operacao("stop_loss", lucro, modo, entrada)
                            print(f"🛑 Stop loss acionado: ${lucro:.2f}")
                            perdas_total += abs(lucro)
                            return

                        if lucro > 0 and is_sellable:
                            ticks = obter_ultimos_precos(ativo, 20)
                            if ticks:
                                velas = transformar_em_velas(ticks, 4)
                                if velas:
                                    decisao = analisar_saida_chatgpt(velas)
                                    if (
                                        decisao == "SAIR"
                                        or lucro >= entrada * TAKE_IMEDIATO
                                    ):
                                        encerrar_contrato(contract_id, token)
                                        registrar_operacao(
                                            "lucro", lucro, modo, entrada
                                        )
                                        print(f"✅ Take profit: ${lucro:.2f}")
                                        lucro_total += lucro
                                        return

                        time.sleep(0.5)

                    except Exception as e:
                        print(f"⚠️ Erro no monitoramento: {e}")
                        traceback.print_exc()
                        time.sleep(1)

                if is_sellable:
                    encerrar_contrato(contract_id, token)
                    print(f"⏰ Timeout encerrando {contract_id}")
                else:
                    print(f"⏰ Timeout, mas contrato ainda não pode ser encerrado.")

            except Exception as e:
                print(f"🚨 Erro na operação: {e}")
                traceback.print_exc()
            finally:
                operacoes_ativas -= 1

        threading.Thread(target=executar, daemon=True).start()

    while status_robo() and lucro_total < meta and perdas_total < stop_loss:
        try:
            if operacoes_ativas >= config["limite"]:
                time.sleep(1)
                continue

            ticks = obter_ultimos_precos(ativo, 20)
            if not ticks or not isinstance(ticks, list) or len(ticks) < 5:
                print("[ERRO] Ticks inválidos ou insuficientes")
                time.sleep(2)
                continue

            velas = transformar_em_velas(ticks, 4)
            if not velas:
                print("[ERRO] Falha ao transformar ticks em velas")
                time.sleep(2)
                continue

            decisao = analisar_entrada_chatgpt(velas, lucro_total, entradas_recentes)
            if decisao in ["AGUARDAR", "PULAR"]:
                time.sleep(3)
                continue

            operacoes_ativas += 1
            operacao_individual()
            time.sleep(cooldown)

        except Exception as e:
            print("🚨 Erro no loop principal:")
            traceback.print_exc()
            time.sleep(5)

    print(f"\n🔴 Bot finalizado | Lucro: ${lucro_total:.2f} de ${meta:.2f}")
    if entradas_recentes:
        acertos = sum(1 for x in entradas_recentes if x == "lucro")
        print(
            f"📊 Estatísticas: {acertos}/{len(entradas_recentes)} ({(acertos/len(entradas_recentes))*100:.1f}%)"
        )

    salvar_status(lucro_total, meta)
    parar_robo()


def monitorar_contratos_antigos(token, entradas_recentes, tempo_min=10, tempo_max=20):
    while config.status_robo():
        agora = time.time()
        for contrato in contratos_abertos[:]:  # cópia da lista
            tempo = agora - contrato["entrada"]

            status_info = status_contrato(contrato["id"], token)
            dados = status_info.get("contract", {})
            status = dados.get("status")
            lucro = dados.get("profit", -999)

            if status != "open":
                contratos_abertos.remove(contrato)
                entradas_recentes.append("lucro" if lucro > 0 else "prejuízo")
                entradas_recentes = entradas_recentes[-10:]  # mantem histórico limitado
                continue

            if tempo >= tempo_min and lucro > 0:
                print(
                    f"⏰ Lucro pequeno identificado (${lucro:.2f}). Fechando contrato atrasado {contrato['id']}..."
                )
                encerrar_contrato(contrato["id"], token)
                contratos_abertos.remove(contrato)

            elif tempo >= tempo_max:
                print(
                    f"⚠️ Contrato {contrato['id']} estagnado há {tempo:.0f}s. Fechando mesmo com prejuízo."
                )
                encerrar_contrato(contrato["id"], token)
                contratos_abertos.remove(contrato)

        time.sleep(1)


def salvar_status(lucro_total, meta):
    """
    Salva o status atual do robô em um arquivo JSON (usado pelo painel).
    """
    try:
        with open("status.json", "w") as f:
            json.dump(
                {
                    "robo_ativo": True,
                    "lucro": round(lucro_total, 2),
                    "meta": round(meta, 2),
                },
                f,
                indent=2,
            )

        print(f"[✔️ STATUS SALVO] Lucro: {lucro_total} | Meta: {meta}")

    except Exception as e:
        print(f"[ERRO AO SALVAR STATUS] {e}")


def transformar_em_velas(ticks, tamanho_vela=4):
    velas = []
    for i in range(0, len(ticks) - tamanho_vela + 1, tamanho_vela):
        bloco = ticks[i : i + tamanho_vela]
        vela = {
            "open": bloco[0],
            "high": max(bloco),
            "low": min(bloco),
            "close": bloco[-1],
        }
        velas.append(vela)
    return velas


def registrar_operacao(resultado, resultado_real, modo, valor):
    """
    Salva os dados de uma operação no arquivo logs.txt de forma segura e eficiente.
    - Limita o total de operações salvas a 100
    - Implementa rotação de logs para evitar crescimento excessivo
    - Tratamento robusto de erros
    - Formato consistente de dados
    - Otimização de I/O
    """
    try:
        # Validação e formatação dos dados
        resultado_real = round(float(resultado_real), 2)
        valor = round(float(valor), 2)
        modo = str(modo).lower() if modo else "desconhecido"

        log = {
            "data": datetime.now().strftime("%Y-%m-%d"),
            "hora": datetime.now().strftime("%H:%M:%S.%f")[:-3],  # milissegundos
            "modo": modo,
            "tipo_operacao": str(resultado).lower(),
            "tipo_resultado": "lucro" if resultado_real > 0 else "prejuízo",
            "valor": valor,
            "resultado_real": resultado_real,
            "timestamp": time.time(),  # Para ordenação precisa
        }

        # Garante que o diretório existe
        os.makedirs("data", exist_ok=True)

        # Lê logs existentes de forma segura
        # Lê logs existentes de forma segura
        logs_existentes = []
        if os.path.exists(LOGS_PATH):
            try:
                with open(LOGS_PATH, "r", encoding="utf-8") as f:
                    for idx, linha in enumerate(f, 1):
                        linha = linha.strip()
                        if not linha:
                            continue
                        try:
                            logs_existentes.append(json.loads(linha))
                        except json.JSONDecodeError as e:
                            print(
                                f"[ERRO JSON linha {idx}] {e} | Conteúdo: {repr(linha)}"
                            )
            except Exception as e:
                print(f"[ERRO LEITURA LOG] {str(e)}")
                logs_existentes = []

        # Adiciona novo log e limita a 100 entradas
        logs_existentes.append(log)
        logs_existentes = sorted(
            logs_existentes[-100:], key=lambda x: x.get("timestamp", 0)
        )

        # Escreve de forma atômica (evita corrupção se o processo for interrompido)
        temp_path = LOGS_PATH + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            for item in logs_existentes:
                # Remove timestamp antes de salvar (não é necessário persistir)
                item.pop("timestamp", None)
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        # Substitui o arquivo original de forma segura
        if os.path.exists(temp_path):
            if os.path.exists(LOGS_PATH):
                os.replace(temp_path, LOGS_PATH)
            else:
                os.rename(temp_path, LOGS_PATH)

        print(
            f"[📝 LOG] {log['hora']} | {modo.upper()} | {log['tipo_resultado'].upper()} | ${resultado_real:.2f}"
        )

    except Exception as e:
        print(f"[ERRO CRÍTICO REGISTRO LOG] {str(e)}")
        # Tenta registrar pelo menos o erro
        try:
            with open("data/erros_registro.log", "a") as f_err:
                f_err.write(
                    f"{datetime.now().isoformat()} - Falha ao registrar operação: {str(e)}\n"
                )
        except:
            pass
