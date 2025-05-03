from inteligencia import carregar_memoria, salvar_memoria, limpar_memoria, client

# === ENTRADA ===
def analisar_entrada_chatgpt(velas, cliente_id="cliente_padrao"):
    try:
        nova_mensagem = {
            "role": "user",
            "content": f"Velas recentes:\n{velas}\n\nCom base nessas velas, responda apenas com: CALL, PUT ou AGUARDAR."
        }

        mensagens = carregar_memoria(cliente_id)
        mensagens.append(nova_mensagem)

        try:
            # Tenta com GPT-4o
            resposta = client.chat.completions.create(
                model="gpt-4o",
                messages=mensagens
            )
        except Exception as erro:
            if "insufficient_quota" in str(erro):
                print("⚠️ GPT-4o sem créditos. Tentando fallback para GPT-3.5-turbo...")
                resposta = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=mensagens
                )
            else:
                raise erro

        conteudo = resposta.choices[0].message.content.strip().upper()
        print(f"[🔎 IA ENTRADA] Resposta: '{conteudo}'")

        salvar_memoria(cliente_id, {"role": "assistant", "content": conteudo})
        return conteudo if conteudo in ["CALL", "PUT"] else "AGUARDAR"

    except Exception as e:
        print(f"[ERRO GPT ENTRADA] {e}")
        return "AGUARDAR"



# === SAÍDA ===
def analisar_saida_chatgpt(velas, cliente_id="cliente_padrao"):
    try:
        nova_mensagem = {
            "role": "user",
            "content": f"Velas após entrada:\n{velas}\n\nCom base nessas velas, devemos SAIR ou MANTER o contrato ativo?"
        }

        mensagens = carregar_memoria(cliente_id)
        mensagens.append(nova_mensagem)

        resposta = client.chat.completions.create(
            model="gpt-4o",
            messages=mensagens
        )

        conteudo = resposta.choices[0].message.content.strip().upper()
        print(f"[🔎 IA SAÍDA] Resposta: '{conteudo}'")

        salvar_memoria(cliente_id, {"role": "assistant", "content": conteudo})
        return conteudo if conteudo in ["SAIR", "MANTER"] else "SAIR"

    except Exception as e:
        print(f"[ERRO GPT SAÍDA] {e}")
        return "SAIR"
