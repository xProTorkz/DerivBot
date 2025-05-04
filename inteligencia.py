import os
import json

MEMORIA_DIR = "memorias"
os.makedirs(MEMORIA_DIR, exist_ok=True)


# === Funções de memória ===
def salvar_memoria(cliente_id, nova_msg):
    path = os.path.join(MEMORIA_DIR, f"{cliente_id}.json")
    historico = carregar_memoria(cliente_id)
    historico.append(nova_msg)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)


import os
import json


def carregar_memoria(cliente_id):
    caminho = f"memorias/{cliente_id}.json"

    if not os.path.exists(caminho):
        return []

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
            if not conteudo:
                return []  # Se estiver vazio
            return json.loads(conteudo)
    except Exception as e:
        print(f"[ERRO MEMÓRIA] Falha ao carregar {caminho}: {e}")
        return []


def limpar_memoria(cliente_id):
    path = os.path.join(MEMORIA_DIR, f"{cliente_id}.json")
    if os.path.exists(path):
        os.remove(path)
