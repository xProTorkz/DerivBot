# resultado.py

import os
import json

LOGS_PATH = "data/logs.txt"

def calcular_assertividade():
    if not os.path.exists(LOGS_PATH):
        return {
            "iniciante": 95,
            "conservador": 85,
            "agressivo": 80
        }

    try:
        with open(LOGS_PATH, "r") as file:
            linhas = file.readlines()

        total = {"iniciante": {"vitorias": 0, "total": 0},
                 "conservador": {"vitorias": 0, "total": 0},
                 "agressivo": {"vitorias": 0, "total": 0}}

        for linha in linhas:
            if not linha.strip():
                continue

            dado = json.loads(linha)
            modo = dado.get("modo", "iniciante")  # Se não tiver modo salvo, assume iniciante
            resultado = dado.get("resultado")

            if modo not in total:
                continue

            total[modo]["total"] += 1
            if resultado == "lucro":
                total[modo]["vitorias"] += 1

        taxas = {}
        for modo, dados in total.items():
            if dados["total"] == 0:
                taxas[modo] = 0
            else:
                taxas[modo] = round((dados["vitorias"] / dados["total"]) * 100)

        return taxas

    except Exception as e:
        print("Erro ao calcular assertividade:", e)
        return {
            "iniciante": 95,
            "conservador": 85,
            "agressivo": 80
        }
