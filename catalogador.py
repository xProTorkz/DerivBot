import httpx
import json
import time
import os
from dotenv import load_dotenv
from inteligencia import carregar_memoria, salvar_memoria

load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

FEW_SHOT_EXEMPLOS = [
    {
        "role": "system",
        "content": "Você é um analista de operações binárias e deve tomar decisões com base em velas, padrões de reversão e indicadores. Responda sempre com: CALL, PUT, ENTRAR, MANTER, SAIR ou AGUARDAR.",
    },
    {
        "role": "user",
        "content": 'Velas:\n[{"open": 681.50, "high": 682.20, "low": 681.40, "close": 682.10}, {"open": 682.10, "high": 682.25, "low": 681.80, "close": 682.15}]\nDecisão: CALL\nResultado: LUCRO',
    },
    {
        "role": "user",
        "content": 'Velas:\n[{"open": 631.60, "high": 631.62, "low": 631.35, "close": 631.40}, {"open": 631.40, "high": 631.42, "low": 630.90, "close": 630.93}]\nDecisão: PUT\nResultado: LUCRO',
    },
    {
        "role": "user",
        "content": 'Velas:\n[{"open": 630.20, "high": 630.35, "low": 630.15, "close": 630.30}, {"open": 630.30, "high": 630.84, "low": 630.28, "close": 630.84}]\nDecisão: CALL\nResultado: LUCRO',
    },
]


def chamar_deepseek(mensagens, max_retries=3):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": mensagens,
        "temperature": 0.2,
    }

    for attempt in range(max_retries):
        print(f"\n[DEBUG] Tentativa {attempt + 1}/{max_retries} para enviar à DeepSeek")

        try:
            with httpx.Client(timeout=35.0) as client:
                response = client.post(DEEPSEEK_URL, headers=headers, json=payload)

            if response.status_code != 200:
                print(
                    f"[ERRO STATUS] HTTP {response.status_code}: {response.text[:200]}"
                )
                continue

            resposta_json = response.json()

            if not resposta_json.get("choices"):
                print("[ERRO] Resposta sem 'choices'")
                continue

            conteudo = resposta_json["choices"][0]["message"]["content"].strip().upper()
            print(f"[DEBUG] Conteúdo final da IA: {conteudo}")

            if conteudo in [
                "CALL",
                "PUT",
                "ENTRAR",
                "MANTER",
                "SAIR",
                "AGUARDAR",
                "PULAR",
            ]:
                return conteudo

            print("[ERRO] Conteúdo inesperado da IA")
            return "AGUARDAR"

        except Exception as e:
            print(f"[ERRO] DeepSeek falhou na tentativa {attempt + 1}: {e}")
            time.sleep(2)

    print("[FALHA TOTAL] Não foi possível obter resposta da DeepSeek")
    return "AGUARDAR"


def analisar_entrada_chatgpt(
    velas, lucro_total, entradas_recentes, cliente_id="cliente_padrao"
):
    if not velas or len(velas) < 4:
        print("[ERRO] Velas insuficientes para análise")
        return "AGUARDAR"

    contexto = {
        "velas": velas[-4:],
        "lucro_total": round(lucro_total, 2),
        "ultimos_resultados": entradas_recentes[-5:],
        "tendencia": "ALTA" if velas[-1]["close"] > velas[-2]["close"] else "BAIXA",
        "volatilidade": round(max(v["high"] - v["low"] for v in velas[-4:]), 2),
    }

    nova_mensagem = {
        "role": "user",
        "content": f"""
ANÁLISE DE ENTRADA - OPÇÕES BINÁRIAS (1M SCALPING)

Contexto atual:
{json.dumps(contexto, indent=2)}

Regras estritas:
1. Se volatilidade > 1.5 → AGUARDAR
2. Se 2+ prejuízos recentes → AGUARDAR
3. Se tendência forte (3+ velas mesma direção) → considerar contra-tendência
4. Padrões de reversão (martelo, estrela cadente) → priorizar
5. Corpos pequenos com sombras grandes → indecisão (AGUARDAR)

Responda APENAS com: ENTRAR, AGUARDAR ou PULAR.
""",
    }

    mensagens = FEW_SHOT_EXEMPLOS + carregar_memoria(cliente_id)
    mensagens.append(nova_mensagem)

    try:
        resposta = chamar_deepseek(mensagens)
        print(f"[IA ENTRADA] Resposta final: {resposta}")
        resposta_valida = (
            resposta if resposta in ["ENTRAR", "AGUARDAR", "PULAR"] else "AGUARDAR"
        )
        salvar_memoria(cliente_id, {"role": "assistant", "content": resposta_valida})
        return resposta_valida
    except Exception as e:
        print(f"[ERRO CRÍTICO IA ENTRADA] {e}")
        return "AGUARDAR"


def analisar_saida_chatgpt(velas, cliente_id="cliente_padrao"):
    if not velas or len(velas) < 2:
        print("[ERRO] Velas insuficientes para análise de saída")
        return "SAIR"

    nova_mensagem = {
        "role": "user",
        "content": f"""
ANÁLISE DE SAÍDA - OPÇÕES BINÁRIAS

Velas desde entrada:
{json.dumps(velas, indent=2)}

Critérios:
1. Se lucro atual >= alvo (70% do potencial) → SAIR
2. Se aparecer padrão de reversão forte → SAIR
3. Se tempo de operação > 80% do período → SAIR
4. Se nova tendência se confirmar → MANTER

Responda APENAS com: SAIR ou MANTER
""",
    }

    mensagens = FEW_SHOT_EXEMPLOS + carregar_memoria(cliente_id)
    mensagens.append(nova_mensagem)

    try:
        conteudo = chamar_deepseek(mensagens)
        resposta = conteudo if conteudo in ["SAIR", "MANTER"] else "SAIR"
        salvar_memoria(cliente_id, {"role": "assistant", "content": resposta})
        print(f"[IA SAÍDA] Decisão final: {resposta}")
        return resposta
    except Exception as e:
        print(f"[ERRO CRÍTICO IA SAÍDA] {e}")
        return "SAIR"
