# config.py

from resultado import calcular_assertividade

# Modo atual selecionado (isso pode ser alterado dinamicamente no painel)
MODO_ATUAL = "iniciante"  # Pode ser: iniciante, conservador, agressivo

# Taxas de assertividade baseadas no histórico de operações (calculadas dinamicamente)
assertividades = calcular_assertividade()

# Configurações do bot
ROBO_ATIVO = False


MODOS = {
    "iniciante": {
        "meta": 20,
        "entrada": 1,
        "stop": 10,
        "nome": f"Iniciante - assertividade média de {assertividades.get('iniciante', 90)}%"
    },
    "conservador": {
        "meta": 50,
        "entrada": 5,
        "stop": 25,
        "nome": f"Conservador - assertividade média de {assertividades.get('conservador', 85)}%"
    },
    "agressivo": {
        "meta": 100,
        "entrada": 10,
        "stop": 50,
        "nome": f"Agressivo - assertividade média de {assertividades.get('agressivo', 80)}%"
    }
}

def get_valores_modo(modo):
    return MODOS.get(modo, MODOS["iniciante"])
# Configurações do aplicativo

# ==========================
# Configurações do robô de trading

def iniciar_robo():
    print("⚙️ Robô está sendo iniciado pelo botão...")
    global ROBO_ATIVO
    ROBO_ATIVO = True
    print("🚀 Robô iniciado!")
    # iniciar loop, thread ou lógica aqui

def parar_robo():
    global ROBO_ATIVO
    ROBO_ATIVO = False
    print("🛑 Robô parado!")
    # encerrar processos, threads, etc

def status_robo():
    return ROBO_ATIVO
