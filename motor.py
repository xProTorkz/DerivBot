# motor.py

import time
import websocket
import json

from config import MODO_ATUAL, MODOS, get_valores_modo
from logs import registrar_operacao
from catalogador import analisar_ticks_chatgpt
from operacoes import comprar_contrato, verificar_lucro, encerrar_contrato

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

# === MOTOR PRINCIPAL ===
def executar_operacao_sniper():
    modo = MODO_ATUAL
    valores = get_valores_modo(modo)

    entrada = valores["entrada"]
    meta = valores["meta"]
    stop = valores["stop"]

    lucro_total = 0
    perdas_total = 0

    print(f"🟢 Iniciando bot no modo {modo.upper()} | Entrada: ${entrada} | Meta: ${meta} | Stop: ${stop}")

    while lucro_total < meta and perdas_total < stop:
        ticks = obter_ultimos_precos()

        if not ticks or len(ticks) < 5:
            print("⏳ Aguardando mais ticks...")
            time.sleep(1)
            continue

        decisao = analisar_ticks_chatgpt(ticks)
        print(f"[IA] Decisão: {decisao}")

        if decisao not in ["CALL", "PUT"]:
            print("🔁 Aguardando nova oportunidade...")
            time.sleep(2)
            continue

        try:
            contract_id = comprar_contrato(entrada, direcao=decisao)
            print(f"📩 Contrato comprado: {contract_id}")
            time.sleep(1.5)

            while True:
                lucro = verificar_lucro(contract_id)
                print(f"💰 Lucro atual: {lucro}")

                if lucro > 0:
                    encerrar_contrato(contract_id)
                    lucro_total += lucro
                    registrar_operacao("lucro", lucro)
                    print(f"✅ Operação com lucro: {lucro}")
                    break
                elif lucro < -entrada:
                    encerrar_contrato(contract_id)
                    perdas_total += entrada
                    registrar_operacao("prejuizo", lucro)
                    print(f"❌ Operação com prejuízo: {lucro}")
                    break

                time.sleep(1)

        except Exception as e:
            registrar_operacao("erro", str(e))
            print(f"[ERRO OPERACIONAL] {e}")
            time.sleep(2)

    print(f"🚫 Bot parou. Lucro total: ${lucro_total} | Perdas totais: ${perdas_total}")
