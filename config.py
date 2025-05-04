# config.py

import json
from resultado import calcular_assertividade

# Caminho do arquivo de status
STATUS_PATH = "status.json"

# Estado global do robô
estado = {
    "robo_ativo": False,
    "modo": None,
    "token": None,
    "meta": 0,
    "tipo_conta": None,
    "lucro_total": 0,
}

# Modo atual selecionado (pode ser alterado dinamicamente no painel)
MODO_ATUAL = "iniciante"  # Pode ser: iniciante, conservador, agressivo

# Taxas de assertividade baseadas no histórico de operações (calculadas dinamicamente)
assertividades = calcular_assertividade()

# Configurações dos modos do robô
MODOS = {
    "iniciante": {
        "meta": 20,
        "entrada": 1,
        "stop": 10,
        "nome": f"Iniciante - assertividade média de {assertividades.get('iniciante', 90)}%",
    },
    "conservador": {
        "meta": 50,
        "entrada": 5,
        "stop": 25,
        "nome": f"Conservador - assertividade média de {assertividades.get('conservador', 85)}%",
    },
    "agressivo": {
        "meta": 100,
        "entrada": 10,
        "stop": 50,
        "nome": f"Agressivo - assertividade média de {assertividades.get('agressivo', 80)}%",
    },
}


# Retorna as configurações do modo atual
def get_valores_modo(modo):
    return MODOS.get(modo, MODOS["iniciante"])


# =============================
# Controle do status do robô


def iniciar_robo():
    print("⚙️ Robô está sendo iniciado pelo botão...")
    estado["robo_ativo"] = True
    salvar_status(estado["lucro_total"], estado["meta"])
    print("🚀 Robô iniciado!")


def parar_robo():
    estado["robo_ativo"] = False
    salvar_status(estado["lucro_total"], estado["meta"])
    print("🛑 Robô parado!")


def status_robo():
    return estado["robo_ativo"]


# =============================
# Persistência de status (usado para sincronizar com frontend)


def salvar_status(lucro_total, meta):
    try:
        with open(STATUS_PATH, "w") as f:
            json.dump(
                {
                    "robo_ativo": estado["robo_ativo"],
                    "lucro": round(lucro_total, 2),
                    "meta": round(meta, 2),
                },
                f,
                indent=2,
            )
        print(f"[✔️ STATUS SALVO] Lucro: {lucro_total} | Meta: {meta}")
    except Exception as e:
        print(f"[ERRO AO SALVAR STATUS] {e}")


def carregar_status():
    try:
        with open(STATUS_PATH, "r") as f:
            dados = json.load(f)
        return dados
    except:
        return {"robo_ativo": False, "lucro": 0, "meta": 0}
