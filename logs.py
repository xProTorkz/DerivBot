# logs.py

import json
from datetime import datetime
from config import MODO_ATUAL
import os

LOGS_PATH = "data/logs.txt"

def registrar_operacao(resultado, valor):
    """Salva o resultado da operação em logs.txt"""
    
    if not os.path.exists("data"):
        os.makedirs("data")

    log = {
        "modo": MODO_ATUAL,
        "resultado": resultado,
        "valor": round(float(valor), 2),
        "hora": datetime.now().strftime("%H:%M:%S")
    }

    try:
        with open(LOGS_PATH, "a") as f:
            f.write(json.dumps(log) + "\n")
        print(f"[LOG] Operação registrada: {log}")
    except Exception as e:
        print(f"[ERRO] Falha ao registrar log: {e}")
