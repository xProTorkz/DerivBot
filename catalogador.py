# catalogador.py

import openai

openai.api_key = "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"
ASSISTANT_ID = "asst_k2ak7MNpC92Mm2LrsywTs0x5"

def analisar_ticks_chatgpt(ticks):
    try:
        # Cria thread
        thread = openai.beta.threads.create()

        # Envia os ticks como mensagem
        prompt = f"""
Análise rápida: os últimos preços foram {ticks}.
Responda apenas com uma palavra: CALL, PUT ou AGUARDE.
Baseie-se em tendência de subida ou queda. Se estiver neutro ou incerto, diga AGUARDE.
        """
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt
        )

        # Executa o assistente GPT-4o
        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        # Espera até terminar (loop simples)
        while True:
            run_status = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if run_status.status == "completed":
                break
            elif run_status.status == "failed":
                return "AGUARDE"
        
        # Recupera resposta
        messages = openai.beta.threads.messages.list(thread_id=thread.id)
        resposta = messages.data[0].content[0].text.value.strip().upper()

        if resposta in ["CALL", "PUT", "AGUARDE"]:
            return resposta
        else:
            return "AGUARDE"

    except Exception as e:
        print(f"[ERRO GPT-4o] {e}")
        return "AGUARDE"

# Função para analisar a saída do ChatGPT
def analisar_saida_chatgpt(ticks, lucro_atual):
    try:
        # Cria thread
        thread = openai.beta.threads.create()

        prompt = f"""
Você é um analista de operações. O contrato está com lucro atual de ${lucro_atual:.2f}.
Os últimos preços foram: {ticks}.
Decida se devemos ENCERRAR agora para garantir lucro ou MANTER a posição mais um pouco.

Responda apenas com: SAIR ou MANTER.
Se houver risco de reversão ou lucro for suficiente, diga SAIR.
Se ainda há potencial de aumento, diga MANTER.
"""

        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt
        )

        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        while True:
            status = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            if status.status == "completed":
                break
            elif status.status == "failed":
                return "SAIR"

        mensagens = openai.beta.threads.messages.list(thread_id=thread.id)
        resposta = mensagens.data[0].content[0].text.value.strip().upper()

        if resposta in ["SAIR", "MANTER"]:
            return resposta
        return "SAIR"

    except Exception as e:
        print(f"[ERRO GPT-4o SAÍDA] {e}")
        return "SAIR"