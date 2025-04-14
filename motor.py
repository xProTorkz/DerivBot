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

def conectar_ws():
    return websocket.create_connection("wss://ws.derivws.com/websockets/v3?app_id=71203")

def autenticar(ws, token):
    ws.send(json.dumps({
        "authorize": token
    }))
    resposta = json.loads(ws.recv())

    if "error" in resposta:
        raise Exception("Erro ao autenticar: " + resposta["error"]["message"])

def obter_status_contrato(contract_id, token):
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

    return {"contract": resposta.get("proposal_open_contract", {})}


estado = {
    "robo_ativo": False,
    "modo": None,
    "token": None,
    "meta": 0,
    "tipo_conta": None,
    "lucro_total": 0  # ← isso aqui precisa existir desde o começo
}

# === Função para pegar últimos ticks do ativo ===
def obter_ultimos_precos(ativo="R_10", quantidade=20):
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
    from logs import registrar_operacao
    from operacoes import comprar_contrato, encerrar_contrato
    from catalogador import analisar_entrada_chatgpt
    from motor import obter_status_contrato, obter_ultimos_precos, transformar_em_velas, salvar_status, estado

    config.ROBO_ATIVO = True
    estado["lucro_total"] = 0  # Zera o lucro ao iniciar

    ativos_por_modo = {
        "iniciante": "R_10",
        "conservador": "R_50",
        "agressivo": "R_100"
    }
    ativo = ativos_por_modo.get(modo, "R_10")

    porcentagem_entrada = {
        "iniciante": 0.05,
        "conservador": 0.10,
        "agressivo": 0.20
    }.get(modo, 0.05)

    entrada = max(1.0, round(meta * porcentagem_entrada, 2))
    stop = meta / 2

    lucro_total = 0
    perdas_total = 0
    operacoes_ativas = 0
    limite_operacoes = {
        "iniciante": 1,
        "conservador": 3,
        "agressivo": 5
    }[modo]

    print(f"\n🟢 Iniciando bot no modo {modo.upper()} | Entrada: ${entrada} | Meta: ${meta} | Stop: ${stop}\n")

    def operacao_individual(direcao):
        nonlocal operacoes_ativas, lucro_total, perdas_total
        print(f"🟢 Iniciando operação individual... Direção: {direcao}")

        try:
            contract_id = comprar_contrato(valor=entrada, token=token, ativo=ativo, direcao=direcao)
            print(f"📩 Contrato {contract_id} comprado em direção: {direcao}")

            while True:
                status_info = obter_status_contrato(contract_id, token)
                contrato = status_info.get("contract", {})
                status = contrato.get("status")

                if status != "open":
                    print("⚠️ Contrato já foi encerrado pela Deriv!")
                    lucro = contrato.get("profit", 0.0)
                    lucro_total += lucro
                    estado["lucro_total"] = lucro_total

                    salvar_status(lucro_total, meta)
                    registrar_operacao(direcao, lucro, modo, entrada)
                    print(f"❌ Contrato finalizado automaticamente com resultado: ${lucro}")
                    break

                lucro = contrato.get("profit", -999)
                print(f"💰 Lucro atual: {lucro}")

                limite_lucro = {
                    "iniciante": entrada * 0.8,
                    "conservador": entrada * 0.5,
                    "agressivo": entrada * 0.2
                }.get(modo, entrada * 0.5)

                if lucro >= limite_lucro:
                    print("✅ Lucro atingido! Encerrando contrato...")
                    encerrar_contrato(contract_id, token)
                    lucro_total += lucro
                    estado["lucro_total"] = lucro_total

                    salvar_status(lucro_total, meta)
                    registrar_operacao(direcao, lucro, modo, entrada)
                    print(f"✅ Contrato encerrado manualmente com lucro: ${lucro:.2f}")
                    break

                time.sleep(1)

        except Exception as e:
            registrar_operacao("erro", 0, modo, entrada)
            print(f"[ERRO OPERACIONAL] {e}")

        operacoes_ativas -= 1

    while config.ROBO_ATIVO and estado["lucro_total"] < meta and perdas_total < stop:
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
            direcao = analisar_entrada_chatgpt(velas)

            if direcao not in ["CALL", "PUT"]:
                print("🔁 Aguardando nova oportunidade...")
                time.sleep(2)
                continue

            operacoes_ativas += 1
            threading.Thread(target=operacao_individual, args=(direcao,)).start()
            time.sleep(2)

        except Exception as e:
            print(f"[ERRO GERAL] {e}")
            time.sleep(2)

    print(f"🚫 Bot parou. Lucro total: ${estado['lucro_total']:.2f}")

def salvar_status(lucro_total, meta):
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

def executar_operacao_sniper(modo, token, meta, tipo_conta):
    config.ROBO_ATIVO = True

    ativos_por_modo = {
        "iniciante": "R_10",
        "conservador": "R_50",
        "agressivo": "R_100"
    }
    ativo = ativos_por_modo.get(modo, "R_10")

    porcentagem_entrada = {
        "iniciante": 0.05,
        "conservador": 0.10,
        "agressivo": 0.20
    }.get(modo, 0.05)

    entrada = max(1.0, round(meta * porcentagem_entrada, 2))
    stop = meta / 2

    lucro_total = 0
    perdas_total = 0
    operacoes_ativas = 0
    limite_operacoes = {
        "iniciante": 1,
        "conservador": 3,
        "agressivo": 5
    }[modo]

    print(f"\n🟢 Iniciando bot no modo {modo.upper()} | Entrada: ${entrada} | Meta: ${meta} | Stop: ${stop}\n")

    def operacao_individual(direcao):
        nonlocal operacoes_ativas, lucro_total, perdas_total
        print(f"🟢 Iniciando operação individual... Direção: {direcao}")

        try:
            contract_id = comprar_contrato(valor=entrada, token=token, ativo=ativo, direcao=direcao)
            print(f"📩 Contrato {contract_id} comprado em direção: {direcao}")

            while True:
                status_info = obter_status_contrato(contract_id, token)
                contrato = status_info.get("contract", {})
                status = contrato.get("status")

                if status != "open":
                    print("⚠️ Contrato já foi encerrado pela Deriv!")
                    lucro = contrato.get("profit", 0.0)
                    lucro_total += lucro
                    estado["lucro_total"] = lucro_total

                    salvar_status(lucro_total, meta)
                    registrar_operacao(direcao, lucro, modo, entrada)
                    print(f"❌ Contrato finalizado automaticamente com resultado: ${lucro}")
                    break

                lucro = contrato.get("profit", -999)
                print(f"💰 Lucro atual: {lucro}")
                limite_lucro = {
                    "iniciante": entrada * 0.8,     # Quer mais segurança, lucro alto
                    "conservador": entrada * 0.5,  # Meio termo
                    "agressivo": entrada * 0.2     # Fecha logo no lucro, entra de novo
                }.get(modo, entrada * 0.5)         # Padrão: 50% se não encontrar o modo


                if lucro >= limite_lucro:
                    print("✅ Lucro atingido! Encerrando contrato...")
                    encerrar_contrato(contract_id, token)
                    lucro_total += lucro
                    estado["lucro_total"] = lucro_total

                    salvar_status(lucro_total, meta)
                    registrar_operacao(direcao, lucro, modo, entrada)
                    print(f"✅ Contrato encerrado manualmente com lucro: ${lucro:.2f}")
                    break

                time.sleep(1)

        except Exception as e:
            registrar_operacao("erro", 0, modo, entrada)
            print(f"[ERRO OPERACIONAL] {e}")

        operacoes_ativas -= 1

    # ⬇️ Agora o LOOP PRINCIPAL (do lado de fora da função acima)
    while config.ROBO_ATIVO and estado["lucro_total"] < meta and perdas_total < stop:
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
            direcao = analisar_entrada_chatgpt(velas)

            if direcao not in ["CALL", "PUT"]:
                print("🔁 Aguardando nova oportunidade...")
                time.sleep(2)
                continue

            operacoes_ativas += 1
            threading.Thread(target=operacao_individual, args=(direcao,)).start()
            time.sleep(2)

        except Exception as e:
            print(f"[ERRO GERAL] {e}")
            time.sleep(2)

    print(f"🚫 Bot parou. Lucro total: ${estado['lucro_total']:.2f}")


    
    
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
    log = {
        "data": datetime.now().strftime("%Y-%m-%d"),
        "hora": datetime.now().strftime("%H:%M:%S"),
        "modo": modo,
        "resultado": resultado.lower(),  # "lucro" ou "prejuízo"
        "resultado_real": round(float(resultado_real), 2),
        "valor": round(float(valor), 2)
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

    # 🔁 Mantém somente as últimas 100 operações
    logs = logs[-100:]

    with open(LOGS_PATH, "w") as f:
        for item in logs:
            f.write(json.dumps(item) + "\n")

    print(f"[📝 LOG] {log['hora']} | {log['resultado'].upper()} | ${log['resultado_real']}")