import json
import uuid
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from urllib.parse import quote

# Configurações
EMAIL_ORIGEM = "pglucas7@gmail.com"
SENHA_APP = "hage qhqk czvf slip"  # ok pra testes
NGROK_URL = "https://3102-200-152-5-73.ngrok-free.app"
LICENCAS_PATH = "licencas.json"

# === GERADOR DE CHAVE COM ESPAÇOS REMOVIDOS ===
def gerar_chave(nome):
    nome_formatado = nome.replace(" ", "")
    return f"{nome_formatado}-{datetime.now().strftime('%d%m%y-%H%M')}-{str(uuid.uuid4())[:6]}"

# === GERA LICENÇA E ENVIA O LINK DE ATIVAÇÃO ===
def gerar_licenca(nome_cliente, email_cliente):
    chave = gerar_chave(nome_cliente)

    # Carregar ou criar licenças
    if not os.path.exists(LICENCAS_PATH):
        licencas = {}
    else:
        with open(LICENCAS_PATH, "r") as f:
            licencas = json.load(f)

    # Estrutura de licença
    licencas[chave] = {
        "usada": False,
        "email": email_cliente,
        "token": "",
        "deriv_account": "",
        "ips": [],
        "hwids": [],
        "ativado_em": ""
    }

    with open(LICENCAS_PATH, "w") as f:
        json.dump(licencas, f, indent=2)

    # Gerar links com a chave codificada
    chave_url = quote(chave)
    link_login = f"{NGROK_URL}/login?chave={chave_url}"
    link_config = f"{NGROK_URL}/configuracao?chave={chave_url}"

    # Enviar e-mail
    enviar_email_ativacao(email_cliente, chave, link_login, link_config)

    print(f"✅ Licença gerada e enviada para: {email_cliente}")
    print(f"🔗 Link Login: {link_login}")
    print(f"🔗 Link Configuração: {link_config}")
    return chave

# === ENVIA E-MAIL DE ATIVAÇÃO COM DOIS BOTÕES ===
def enviar_email_ativacao(destinatario, chave, link_login, link_config):
    assunto = "✅ Acesso Liberado - Robô Deriv"
    corpo = f"""
    <h2>Bem-vindo ao Robô Deriv, {destinatario.split('@')[0].capitalize()}!</h2>
    <p>Siga as etapas abaixo para ativar seu acesso:</p>

    <p>
      <a href="{link_login}" style="padding:12px 24px; background:#00d67b; color:white; text-decoration:none; border-radius:6px; display:inline-block;" target="_blank">
        1️⃣ Criar Conta e Vincular Chave
      </a>
    </p>

    <p>
      <a href="{link_config}" style="padding:12px 24px; background:#ff444f; color:white; text-decoration:none; border-radius:6px; display:inline-block;" target="_blank">
        2️⃣ Validar Token e Ativar Robô
      </a>
    </p>

    <br>
    <p><strong>🔐 Chave vinculada:</strong> {chave}</p>
    <p style="color:#999;">⚠️ Seu acesso será validado com base no IP e dispositivo utilizados.</p>
    <p>Em caso de dúvidas, fale com o suporte.</p>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = EMAIL_ORIGEM
    msg["To"] = destinatario

    parte_html = MIMEText(corpo, "html")
    msg.attach(parte_html)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
        servidor.login(EMAIL_ORIGEM, SENHA_APP)
        servidor.sendmail(EMAIL_ORIGEM, destinatario, msg.as_string())

# === TESTE MANUAL ===
if __name__ == "__main__":
    nome = input("Nome do cliente (ex: Lucas): ")
    email = input("E-mail do cliente: ")
    gerar_licenca(nome, email)
