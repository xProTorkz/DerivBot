# 📧 Configuração de Email Automático - DerivBot

## 🚨 **AÇÃO NECESSÁRIA**

**O sistema detectou que você precisa configurar seu email real para enviar as instruções automaticamente.**

## ⚡ **Configuração Rápida (5 minutos)**

### **1. Acesse o Painel Admin**

```
http://localhost:5000/admin
```

### **2. Vá na aba "📧 Email Config"**

### **3. Configure seu Gmail (Recomendado):**

- **Servidor SMTP:** `smtp.gmail.com` (já preenchido)
- **Porta:** `587` (já preenchido)
- **Email:** Substitua `SEU_EMAIL@gmail.com` pelo seu Gmail real
- **Senha:** Substitua `SUA_SENHA_DE_APP` pela senha de app do Gmail

### **4. Como Obter Senha de App do Gmail:**

**🔗 Link Direto:** https://myaccount.google.com/apppasswords

**Passo a passo:**

1. **Acesse:** https://myaccount.google.com/security
2. **Ative a verificação em 2 etapas** (se não estiver ativa)
3. **Vá em "Senhas de app"**
4. **Selecione:**
   - App: `Email`
   - Dispositivo: `Computador Windows`
5. **Copie a senha gerada** (16 caracteres)
6. **Use essa senha** no campo "Senha" do painel admin

### **3. Para Outros Provedores**

#### **Outlook/Hotmail:**

- **Servidor:** `smtp-mail.outlook.com`
- **Porta:** `587`
- **Usar senha normal** da conta

#### **Yahoo:**

- **Servidor:** `smtp.mail.yahoo.com`
- **Porta:** `587`
- **Criar senha de app** similar ao Gmail

#### **Provedor Personalizado:**

- **Consulte a documentação** do seu provedor de email
- **Geralmente usa porta 587** com STARTTLS

## 🧪 **Testar Configuração**

1. **No painel admin, aba "📧 Email Config"**
2. **Clique em "Testar Email"**
3. **Digite um email de teste**
4. **Verifique se recebeu o email**

## 🚀 **Funcionamento Automático**

### **Quando uma licença é criada:**

1. ✅ **Sistema gera a licença**
2. ✅ **Cria email HTML com instruções**
3. ✅ **Envia automaticamente para o cliente**
4. ✅ **Registra no log se foi enviado**

### **O email contém:**

- 🎯 **Código da licença**
- 📋 **Instruções passo a passo**
- 🔗 **Links diretos para obter tokens**
- ⚠️ **Dicas importantes**
- 📞 **Informações de suporte**

## 🔧 **Configuração Manual (Avançado)**

Se preferir editar diretamente o arquivo:

```json
{
  "email": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "email_user": "seu_email@gmail.com",
    "email_pass": "sua_senha_de_app"
  },
  "auto_send_email": true
}
```

**Arquivo:** `data/admin_config.json`

## ⚠️ **Importante**

- ✅ **Sempre teste** antes de usar em produção
- 🔒 **Use senhas de app**, não senhas normais
- 📧 **Verifique spam** se não receber emails
- 🔄 **Reinicie o servidor** após mudanças manuais

## 🆘 **Solução de Problemas**

### **Email não enviado:**

1. Verificar configurações SMTP
2. Testar com email de teste
3. Verificar logs do sistema
4. Confirmar senha de app

### **Email vai para spam:**

1. Configurar SPF/DKIM no domínio
2. Usar email profissional
3. Evitar palavras suspeitas

### **Erro de autenticação:**

1. Verificar senha de app
2. Confirmar 2FA ativo
3. Tentar recriar senha de app

---

**🎉 Após configurar, todas as licenças criadas enviarão automaticamente as instruções por email!**
