import time
import websocket
import json
import config
import threading
import os
import sys

from logs import registrar_operacao
from datetime import datetime
from operacoes import comprar_contrato, encerrar_contrato, verificar_lucro
from catalogador import analisar_entrada_chatgpt

LOGS_PATH = "data/logs.txt"
estado = {
    "robo_ativo": False,
    "modo": None,
    "token": None,
    "meta": 0,
    "tipo_conta": None,
    "lucro_total": 0.0  # Garantido desde o início
}

contratos_abertos = []  # Lista de contratos abertos monitorados


def conectar_ws():
    return websocket.create_connection("wss://ws.derivws.com/websockets/v3?app_id=71203")

def autenticar(ws, token):
    ws.send(json.dumps({
        "authorize": token
    }))
    resposta = json.loads(ws.recv())

    if "error" in resposta:
        raise Exception("Erro ao autenticar: " + resposta["error"]["message"])

# ================== FUNÇÃO DE CONSULTA ===================
def obter_status_contrato(contract_id, token):
    try:
        ws = conectar_ws()
        autenticar(ws, token)

        ws.send(json.dumps({
            "proposal_open_contract": 1,
            "contract_id": contract_id
        }))

        resposta = json.loads(ws.recv())
        ws.close()

        if "error" in resposta:
            raise Exception("Erro ao consultar status do contrato: " + resposta["error"]["message"])

        contrato = resposta.get("proposal_open_contract")
        if not contrato:
            raise Exception("Contrato não encontrado ou resposta inválida.")

        return {"contract": contrato}

    except Exception as e:
        print(f"[ERRO] Falha ao obter status do contrato {contract_id}: {e}")
        return {"contract": {}, "erro": str(e)}

# === Função para pegar últimos ticks do ativo ===
def obter_ultimos_precos(ativo="1HZ10V", quantidade=20):
    try:
        ws = websocket.WebSocket()
        ws.connect("wss://ws.derivws.com/websockets/v3?app_id=71203")

        ws.send(json.dumps({
            "ticks_history": ativo,
            "count": quantidade,
            "end": "latest",
            "style": "ticks"
        }))

        resposta = json.loads(ws.recv())
        ws.close()

        if "history" in resposta and "prices" in resposta["history"]:
            return resposta["history"]["prices"]
        else:
            return []
    except Exception as e:
        print(f"[ERRO TICKS] {e}")
        return []

def consultar_saldo(token):
    try:
        ws = websocket.WebSocket()
        ws.connect("wss://ws.derivws.com/websockets/v3?app_id=71203")

        # Autoriza com o token
        ws.send(json.dumps({
            "authorize": token
        }))
        ws.recv()  # resposta de autorização

        # Solicita saldo
        ws.send(json.dumps({
            "balance": 1,
            "subscribe": 0
        }))
        resposta = json.loads(ws.recv())
        ws.close()

        return resposta["balance"]["balance"]
    except Exception as e:
        print(f"[ERRO SALDO] {e}")
        return 0
    
def verificar_status_contrato(contract_id, token):
    try:
        ws = websocket.WebSocket()
        ws.connect("wss://ws.derivws.com/websockets/v3?app_id=71287")

        ws.send(json.dumps({"authorize": token}))
        ws.recv()  # ignora resposta da autorização

        ws.send(json.dumps({
            "contract": contract_id,
            "subscribe": 1
        }))

        data = json.loads(ws.recv())
        ws.close()

        status = data.get("contract", {}).get("status", "unknown")
        return status
    except Exception as e:
        print(f"[ERRO STATUS CONTRATO] {e}")
        return "erro"
    
# === MOTOR PRINCIPAL ===
def executar_operacao_sniper(modo, token, meta, tipo_conta):
    config.ROBO_ATIVO = True
    threading.Thread(target=monitorar_contratos_antigos, args=(token,), daemon=True).start()

    estado["lucro_total"] = 0

    ativos_por_modo = {
        "iniciante": "1HZ10V",
        "conservador": "1HZ50V",
        "agressivo": "1HZ100V"
    }
    ativo = ativos_por_modo.get(modo, "1HZ10V")

    porcentagem_entrada = {
        "iniciante": 0.05,
        "conservador": 0.10,
        "agressivo": 0.20
    }.get(modo, 0.05)

    entrada = max(1.0, round(meta * porcentagem_entrada, 2))
    stop = meta / 2
    limite_operacoes = {
        "iniciante": 3,
        "conservador": 5,
        "agressivo": 10
    }[modo]

    lucro_total = 0
    perdas_total = 0
    operacoes_ativas = 0

    print(f"\n🟢 Iniciando bot no modo {modo.upper()} | Entrada: ${entrada} | Meta: ${meta} | Stop: ${stop}\n")

    def operacao_individual():
        nonlocal operacoes_ativas, lucro_total, perdas_total
        print(f"🟢 Iniciando operação MULTIPLIER...")

        try:
            contract_id = comprar_contrato(valor=entrada, token=token, ativo=ativo, modo=modo)
            print(f"📩 Contrato MULTIPLIER {contract_id} comprado.")
            # Salva o contrato com timestamp
            contratos_abertos.append({
                "id": contract_id,
                "entrada": time.time()
            })


            while True:
                status_info = obter_status_contrato(contract_id, token)
                contrato = status_info.get("contract", {})
                status = contrato.get("status")

                if status != "open":
                    lucro = contrato.get("profit", 0.0)
                    lucro_total += lucro
                    estado["lucro_total"] = lucro_total
                    salvar_status(lucro_total, meta)
                    registrar_operacao("fechado", lucro, modo, entrada)
                    print(f"❌ Contrato encerrado automaticamente com resultado: ${lucro:.2f}")
                    break

                lucro = contrato.get("profit", -999)
                print(f"💰 Lucro atual: ${lucro:.2f}")
                
                stop_por_operacao = entrada * 0.5  # 5% de perda por operação

                if lucro <= -stop_por_operacao:
                    print(f"🚨 Stop por operação atingido! Prejuízo: ${lucro:.2f}")
                    encerrar_contrato(contract_id, token)
                    perdas_total += abs(lucro)
                    lucro_total += lucro
                    estado["lucro_total"] = lucro_total
                    salvar_status(lucro_total, meta)
                    registrar_operacao("stop_loss", lucro, modo, entrada)
                    print(f"❌ Contrato encerrado por stop individual: ${lucro:.2f}")
                    break


                limite_lucro = {
                    "iniciante": entrada * 0.02,
                    "conservador": entrada * 0.05,
                    "agressivo": entrada * 0.10
                }.get(modo, entrada * 0.20)

                if lucro >= limite_lucro:
                    print("✅ Lucro atingido! Vendendo contrato...")
                    encerrar_contrato(contract_id, token)
                    lucro_total += lucro
                    estado["lucro_total"] = lucro_total
                    salvar_status(lucro_total, meta)
                    registrar_operacao("lucro", lucro, modo, entrada)
                    print(f"✅ Contrato encerrado com lucro: ${lucro:.2f}")
                    break

                time.sleep(1)

        except Exception as e:
            registrar_operacao("erro", 0, modo, entrada)
            print(f"[ERRO OPERACIONAL] {e}")

        operacoes_ativas -= 1

    while config.ROBO_ATIVO and lucro_total < meta and perdas_total < stop:
        if operacoes_ativas >= limite_operacoes:
            time.sleep(1)
            continue

        try:
            ticks = obter_ultimos_precos(ativo=ativo, quantidade=20)
            if not ticks or len(ticks) < 5:
                print("⏳ Aguardando mais ticks...")
                time.sleep(1)
                continue

            velas = transformar_em_velas(ticks, tamanho_vela=4)
            decisao = analisar_entrada_chatgpt(velas)

            if "evitar" in str(decisao).lower():
                print("🔁 IA sugeriu aguardar. Aguardando nova oportunidade...")
                time.sleep(2)
                continue

            operacoes_ativas += 1
            threading.Thread(target=operacao_individual).start()
            time.sleep(2)

        except Exception as e:
            print(f"[ERRO GERAL] {e}")
            time.sleep(2)

    print(f"🚫 Bot parou. Lucro total: ${lucro_total:.2f}")

def monitorar_contratos_antigos(token, tempo_min=10, tempo_max=20):
    while config.ROBO_ATIVO:
        agora = time.time()
        for contrato in contratos_abertos[:]:  # cópia da lista
            tempo = agora - contrato["entrada"]

            status_info = obter_status_contrato(contrato["id"], token)
            dados = status_info.get("contract", {})
            status = dados.get("status")
            lucro = dados.get("profit", -999)

            if status != "open":
                contratos_abertos.remove(contrato)
                continue

            if tempo >= tempo_min and lucro > 0:
                print(f"⏰ Lucro pequeno identificado (${lucro:.2f}). Fechando contrato atrasado {contrato['id']}...")
                encerrar_contrato(contrato["id"], token)
                contratos_abertos.remove(contrato)

            elif tempo >= tempo_max:
                print(f"⚠️ Contrato {contrato['id']} estagnado há {tempo:.0f}s. Fechando mesmo com prejuízo.")
                encerrar_contrato(contrato["id"], token)
                contratos_abertos.remove(contrato)

        time.sleep(1)


def salvar_status(lucro_total, meta):
    """
    Salva o status atual do robô em um arquivo JSON (usado pelo painel).
    """
    try:
        with open("status.json", "w") as f:
            json.dump({
                "robo_ativo": True,
                "lucro": round(lucro_total, 2),
                "meta": round(meta, 2)
            }, f, indent=2)

        print(f"[✔️ STATUS SALVO] Lucro: {lucro_total} | Meta: {meta}")

    except Exception as e:
        print(f"[ERRO AO SALVAR STATUS] {e}")
      
def transformar_em_velas(ticks, tamanho_vela=4):
    velas = []
    for i in range(0, len(ticks) - tamanho_vela + 1, tamanho_vela):
        bloco = ticks[i:i + tamanho_vela]
        vela = {
            "open": bloco[0],
            "high": max(bloco),
            "low": min(bloco),
            "close": bloco[-1]
        }
        velas.append(vela)
    return velas
   
def registrar_operacao(resultado, resultado_real, modo, valor):
    """
    Salva os dados de uma operação no arquivo logs.txt
    Limita o total de operações salvas a 100.
    """
    resultado_real = round(float(resultado_real), 2)
    valor = round(float(valor), 2)

    log = {
        "data": datetime.now().strftime("%Y-%m-%d"),
        "hora": datetime.now().strftime("%H:%M:%S"),
        "tipo": "lucro" if resultado_real > 0 else "prejuízo",  # ✅ esse é o tipo financeiro
        "valor": valor,
        "resultado_real": resultado_real
    }

    if not os.path.exists("data"):
        os.makedirs("data")

    logs = []
    if os.path.exists(LOGS_PATH):
        with open(LOGS_PATH, "r") as f:
            for linha in f:
                if linha.strip():
                    try:
                        logs.append(json.loads(linha.strip()))
                    except:
                        continue

    logs.append(log)
    logs = logs[-100:]

    with open(LOGS_PATH, "w") as f:
        for item in logs:
            f.write(json.dumps(item) + "\n")

    print(f"[📝 LOG] {log['hora']} | {log['tipo'].upper()} | ${log['resultado_real']}")
