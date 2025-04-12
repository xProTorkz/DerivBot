# logs.py

import json
from datetime import datetime
from config import MODO_ATUAL
import os

LOGS_PATH = "data/logs.txt"

# logs.py
import json
from datetime import datetime
from constantes import LOGS_PATH

def registrar_operacao(resultado, lucro_ou_erro, modo="desconhecido", valor_entrada=0):
    try:
        registro = {
            "modo": modo,
            "resultado": resultado,
            "valor": round(float(valor_entrada), 2),
            "resultado_real": round(float(lucro_ou_erro), 2),
            "hora": datetime.now().strftime("%H:%M:%S")
        }

        print(f"[LOG] Operação registrada: {registro}")

        with open(LOGS_PATH, "a") as f:
            f.write(json.dumps(registro) + "\n")
    except Exception as e:
        print(f"[ERRO LOG]: {e}")
