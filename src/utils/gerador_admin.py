"""
Sistema de Geração e Gerenciamento de Licenças - Admin
"""

import json
import os
import secrets
import string
import smtplib
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class GeradorLicencasAdmin:
    def __init__(self):
        self.licencas_file = "data/licencas.json"
        self.config_file = "data/admin_config.json"
        self.ensure_files_exist()

    def ensure_files_exist(self):
        """Garante que os arquivos necessários existam"""
        os.makedirs("data", exist_ok=True)

        if not os.path.exists(self.licencas_file):
            with open(self.licencas_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

        if not os.path.exists(self.config_file):
            config_inicial = {
                "email": {
                    "smtp_server": "",
                    "smtp_port": 587,
                    "email_user": "",
                    "email_pass": "",
                },
                "api_key": self.generate_api_key(),
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_inicial, f, indent=2)

    def generate_license_code(self) -> str:
        """Gera um código único de licença"""
        # Formato: DERIVBOT-XXXX-XXXX
        chars = string.ascii_uppercase + string.digits
        part1 = "".join(secrets.choice(chars) for _ in range(4))
        part2 = "".join(secrets.choice(chars) for _ in range(4))
        return f"DERIVBOT-{part1}-{part2}"

    def generate_api_key(self) -> str:
        """Gera uma chave API única"""
        return secrets.token_urlsafe(32)

    def calculate_expiry_date(self, tipo: str) -> str:
        """Calcula a data de expiração baseada no tipo"""
        hoje = datetime.now()

        if tipo == "vitalicio":
            return "VITALICIO"
        elif tipo == "anual":
            expiry = hoje + timedelta(days=365)
            return expiry.strftime("%Y-%m-%d")
        elif tipo == "mensal":
            expiry = hoje + timedelta(days=30)
            return expiry.strftime("%Y-%m-%d")
        elif tipo == "teste":
            expiry = hoje + timedelta(days=7)
            return expiry.strftime("%Y-%m-%d")
        else:
            return "VITALICIO"

    def create_license(
        self, tipo: str, email: str = "", nome: str = "", observacoes: str = ""
    ) -> Tuple[bool, str, str]:
        """
        Cria uma nova licença

        Returns:
            Tuple[bool, str, str]: (sucesso, codigo_licenca, mensagem)
        """
        try:
            # Gerar código único
            codigo_licenca = self.generate_license_code()

            # Verificar se já existe (muito improvável, mas por segurança)
            licencas = self.load_licenses()
            while any(
                lic.get("codigo_licenca") == codigo_licenca for lic in licencas.values()
            ):
                codigo_licenca = self.generate_license_code()

            # Calcular validade
            validade = self.calculate_expiry_date(tipo)

            # Criar licença
            licenca_key = f"licenca_{len(licencas) + 1:03d}"
            nova_licenca = {
                "codigo_licenca": codigo_licenca,
                "status": "ativa",
                "plano": tipo,
                "validade": validade,
                "hwid": "",  # Será preenchido quando vinculado
                "ip": "",  # Será preenchido quando vinculado
                "deriv_real": "",  # Será preenchido quando vinculado
                "deriv_demo": "",  # Será preenchido quando vinculado
                "token_deriv_real": "",  # Será preenchido quando vinculado
                "token_deriv_demo": "",  # Será preenchido quando vinculado
                "data_criacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_vinculacao": "",  # Será preenchido quando vinculado
                "cliente_email": email,
                "cliente_nome": nome,
                "observacoes": observacoes,
            }

            # Salvar licença
            licencas[licenca_key] = nova_licenca
            self.save_licenses(licencas)

            logger.info(f"Nova licença criada: {codigo_licenca} - Tipo: {tipo}")
            return True, codigo_licenca, "Licença criada com sucesso"

        except Exception as e:
            logger.error(f"Erro ao criar licença: {e}")
            return False, "", f"Erro ao criar licença: {str(e)}"

    def load_licenses(self) -> Dict:
        """Carrega todas as licenças"""
        try:
            with open(self.licencas_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erro ao carregar licenças: {e}")
            return {}

    def save_licenses(self, licencas: Dict):
        """Salva as licenças no arquivo"""
        try:
            with open(self.licencas_file, "w", encoding="utf-8") as f:
                json.dump(licencas, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar licenças: {e}")

    def get_license_stats(self) -> Dict:
        """Obtém estatísticas das licenças"""
        licencas = self.load_licenses()
        hoje = datetime.now().strftime("%Y-%m-%d")

        total = len(licencas)
        ativas = sum(1 for lic in licencas.values() if lic.get("status") == "ativa")
        expiradas = sum(1 for lic in licencas.values() if self.is_license_expired(lic))
        hoje_geradas = sum(
            1
            for lic in licencas.values()
            if lic.get("data_criacao", "").startswith(hoje)
        )

        return {
            "total": total,
            "ativas": ativas,
            "expiradas": expiradas,
            "hoje": hoje_geradas,
        }

    def is_license_expired(self, licenca: Dict) -> bool:
        """Verifica se uma licença está expirada"""
        validade = licenca.get("validade", "")
        if validade == "VITALICIO":
            return False

        try:
            data_validade = datetime.strptime(validade, "%Y-%m-%d")
            return datetime.now() > data_validade
        except:
            return False

    def get_recent_licenses(self, limit: int = 10) -> List[Dict]:
        """Obtém as licenças mais recentes"""
        licencas = self.load_licenses()

        # Converter para lista e ordenar por data de criação
        licencas_list = []
        for key, lic in licencas.items():
            lic_copy = lic.copy()
            lic_copy["key"] = key

            # Determinar status real
            if self.is_license_expired(lic_copy):
                lic_copy["status"] = "expirada"

            # Adicionar nome do cliente se disponível
            if lic_copy.get("cliente_nome"):
                lic_copy["cliente"] = lic_copy["cliente_nome"]
            elif lic_copy.get("cliente_email"):
                lic_copy["cliente"] = lic_copy["cliente_email"]
            else:
                lic_copy["cliente"] = "N/A"

            licencas_list.append(lic_copy)

        # Ordenar por data de criação (mais recente primeiro)
        licencas_list.sort(key=lambda x: x.get("data_criacao", ""), reverse=True)

        return licencas_list[:limit]

    def delete_license(self, codigo_licenca: str) -> Tuple[bool, str]:
        """Exclui uma licença"""
        try:
            licencas = self.load_licenses()

            # Encontrar e remover a licença
            licenca_key = None
            for key, lic in licencas.items():
                if lic.get("codigo_licenca") == codigo_licenca:
                    licenca_key = key
                    break

            if licenca_key:
                del licencas[licenca_key]
                self.save_licenses(licencas)
                logger.info(f"Licença excluída: {codigo_licenca}")
                return True, "Licença excluída com sucesso"
            else:
                return False, "Licença não encontrada"

        except Exception as e:
            logger.error(f"Erro ao excluir licença: {e}")
            return False, f"Erro ao excluir licença: {str(e)}"

    def load_config(self) -> Dict:
        """Carrega a configuração do admin"""
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erro ao carregar configuração: {e}")
            return {}

    def save_config(self, config: Dict):
        """Salva a configuração do admin"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar configuração: {e}")

    def save_email_config(
        self, smtp_server: str, smtp_port: int, email_user: str, email_pass: str
    ) -> Tuple[bool, str]:
        """Salva a configuração de email"""
        try:
            config = self.load_config()
            config["email"] = {
                "smtp_server": smtp_server,
                "smtp_port": smtp_port,
                "email_user": email_user,
                "email_pass": email_pass,
            }
            self.save_config(config)
            return True, "Configuração salva com sucesso"
        except Exception as e:
            logger.error(f"Erro ao salvar configuração de email: {e}")
            return False, f"Erro: {str(e)}"

    def get_email_template(self, codigo_licenca: str, nome_cliente: str = "") -> str:
        """Gera o template de email com instruções"""
        nome = nome_cliente if nome_cliente else "Cliente"

        template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
        .license-code {{ background: #ffae42; color: #1a1a2e; padding: 15px; text-align: center; font-size: 24px; font-weight: bold; border-radius: 8px; margin: 20px 0; letter-spacing: 2px; }}
        .step {{ background: white; margin: 15px 0; padding: 20px; border-radius: 8px; border-left: 4px solid #ffae42; }}
        .step-number {{ background: #ffae42; color: white; width: 30px; height: 30px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-weight: bold; margin-right: 15px; }}
        .warning {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        .btn {{ background: #ffae42; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 DerivBot - Sua Licença Está Pronta!</h1>
            <p>Bem-vindo ao futuro do trading automatizado</p>
        </div>
        
        <div class="content">
            <h2>Olá, {nome}!</h2>
            <p>Parabéns pela aquisição do <strong>DerivBot</strong>! Sua licença foi gerada com sucesso.</p>
            
            <div class="license-code">
                {codigo_licenca}
            </div>
            
            <p><strong>⚠️ IMPORTANTE:</strong> Guarde este código com segurança. Você precisará dele para ativar o sistema.</p>
            
            <h3>📋 Instruções de Ativação:</h3>
            
            <div class="step">
                <span class="step-number">1</span>
                <div style="display: inline-block; vertical-align: top; width: calc(100% - 50px);">
                    <h4>Obtenha seus Tokens da Deriv</h4>
                    <p>Acesse <a href="https://app.deriv.com/account/api-token?lang=PT" target="_blank" class="btn">🔗 Deriv API Tokens</a></p>
                    <p><strong>Caminho alternativo:</strong> deriv.com → Criar conta → Configurações de conta → Token de API</p>
                    <p><strong>Permissões necessárias:</strong> ✅ Ler ✅ Negociar ✅ Informações de trading</p>
                </div>
            </div>
            
            <div class="step">
                <span class="step-number">2</span>
                <div style="display: inline-block; vertical-align: top; width: calc(100% - 50px);">
                    <h4>Execute o DerivBot</h4>
                    <p>Clique duas vezes no arquivo <code>executar_derivbot.bat</code></p>
                    <p>O sistema abrirá automaticamente no seu navegador.</p>
                </div>
            </div>
            
            <div class="step">
                <span class="step-number">3</span>
                <div style="display: inline-block; vertical-align: top; width: calc(100% - 50px);">
                    <h4>Faça Login</h4>
                    <p>Na tela de login, insira:</p>
                    <ul>
                        <li><strong>Código de Licença:</strong> {codigo_licenca}</li>
                        <li><strong>Token Real:</strong> Seu token da conta real (obrigatório)</li>
                        <li><strong>Token Demo:</strong> Seu token da conta demo (opcional)</li>
                    </ul>
                </div>
            </div>
            
            <div class="step">
                <span class="step-number">4</span>
                <div style="display: inline-block; vertical-align: top; width: calc(100% - 50px);">
                    <h4>Comece a Lucrar!</h4>
                    <p>Após o login, configure suas estratégias e deixe o bot trabalhar para você!</p>
                </div>
            </div>
            
            <div class="warning">
                <h4>⚠️ Dicas Importantes:</h4>
                <ul>
                    <li>Sempre teste primeiro com a conta demo</li>
                    <li>Comece com valores baixos</li>
                    <li>Monitore os resultados regularmente</li>
                    <li>Trading envolve riscos - invista com responsabilidade</li>
                </ul>
            </div>
            
            <h3>🆘 Precisa de Ajuda?</h3>
            <p>Nossa equipe está pronta para ajudar:</p>
            <ul>
                <li>📧 Email: suporte@derivbot.com</li>
                <li>💬 WhatsApp: +55 11 99999-9999</li>
                <li>🌐 Site: www.derivbot.com</li>
            </ul>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="https://app.deriv.com/account/api-token?lang=PT" target="_blank" class="btn">🚀 Obter Tokens Agora</a>
            </div>
        </div>
        
        <div class="footer">
            <p>© 2024 DerivBot - Todos os direitos reservados</p>
            <p>Este email foi enviado automaticamente. Não responda a este email.</p>
        </div>
    </div>
</body>
</html>
        """

        return template.strip()

    def send_email(
        self, codigo_licenca: str, email_destino: str, nome_cliente: str = ""
    ) -> Tuple[bool, str]:
        """Envia email com instruções da licença"""
        try:
            config = self.load_config()
            email_config = config.get("email", {})

            if not all(
                [
                    email_config.get("smtp_server"),
                    email_config.get("email_user"),
                    email_config.get("email_pass"),
                ]
            ):
                return False, "Configuração de email não encontrada"

            # Importar classes de email dinamicamente
            try:
                from email.mime.text import MimeText
                from email.mime.multipart import MimeMultipart
            except ImportError:
                try:
                    from email.MIMEText import MIMEText as MimeText
                    from email.MIMEMultipart import MIMEMultipart as MimeMultipart
                except ImportError:
                    return False, "Biblioteca de email não disponível"

            # Criar mensagem
            msg = MimeMultipart("alternative")
            msg["Subject"] = f"🚀 DerivBot - Sua Licença {codigo_licenca} Está Pronta!"
            msg["From"] = email_config["email_user"]
            msg["To"] = email_destino

            # Criar conteúdo HTML
            html_content = self.get_email_template(codigo_licenca, nome_cliente)
            html_part = MimeText(html_content, "html", "utf-8")
            msg.attach(html_part)

            # Enviar email
            with smtplib.SMTP(
                email_config["smtp_server"], email_config["smtp_port"]
            ) as server:
                server.starttls()
                server.login(email_config["email_user"], email_config["email_pass"])
                server.send_message(msg)

            logger.info(
                f"Email enviado para {email_destino} - Licença: {codigo_licenca}"
            )
            return True, "Email enviado com sucesso"

        except Exception as e:
            logger.error(f"Erro ao enviar email: {e}")
            return False, f"Erro ao enviar email: {str(e)}"

    def test_email_config(self, email_destino: str) -> Tuple[bool, str]:
        """Testa a configuração de email"""
        try:
            config = self.load_config()
            email_config = config.get("email", {})

            if not all(
                [
                    email_config.get("smtp_server"),
                    email_config.get("email_user"),
                    email_config.get("email_pass"),
                ]
            ):
                return False, "Configuração de email incompleta"

            # Importar classes de email dinamicamente
            try:
                from email.mime.text import MimeText
            except ImportError:
                try:
                    from email.MIMEText import MIMEText as MimeText
                except ImportError:
                    return False, "Biblioteca de email não disponível"

            # Criar mensagem de teste
            msg = MimeText(
                "Este é um email de teste do sistema DerivBot Admin.", "plain", "utf-8"
            )
            msg["Subject"] = "🧪 Teste de Configuração - DerivBot Admin"
            msg["From"] = email_config["email_user"]
            msg["To"] = email_destino

            # Enviar email
            with smtplib.SMTP(
                email_config["smtp_server"], email_config["smtp_port"]
            ) as server:
                server.starttls()
                server.login(email_config["email_user"], email_config["email_pass"])
                server.send_message(msg)

            return True, "Email de teste enviado com sucesso"

        except Exception as e:
            logger.error(f"Erro no teste de email: {e}")
            return False, f"Erro: {str(e)}"

    def validate_api_key(self, api_key: str) -> bool:
        """Valida uma chave API"""
        config = self.load_config()
        return config.get("api_key") == api_key

    def generate_new_api_key(self) -> str:
        """Gera uma nova chave API"""
        new_key = self.generate_api_key()
        config = self.load_config()
        config["api_key"] = new_key
        self.save_config(config)
        return new_key


# Instância global
gerador_admin = GeradorLicencasAdmin()
