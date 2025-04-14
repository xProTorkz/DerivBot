import os
import json
from openai import OpenAI

# Inicializa o client com a chave da API
client = OpenAI(api_key="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")

MEMORIA_DIR = "memorias"
os.makedirs(MEMORIA_DIR, exist_ok=True)

# === Funções de memória ===
def salvar_memoria(cliente_id, nova_msg):
    path = os.path.join(MEMORIA_DIR, f"{cliente_id}.json")
    historico = carregar_memoria(cliente_id)
    historico.append(nova_msg)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)

def carregar_memoria(cliente_id):
    path = os.path.join(MEMORIA_DIR, f"{cliente_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return [{"role": "system", "content": "Você é um analista de mercado de opções binárias."}]

def limpar_memoria(cliente_id):
    path = os.path.join(MEMORIA_DIR, f"{cliente_id}.json")
    if os.path.exists(path):
        os.remove(path)
