# 🔧 DerivBot - Painel Administrativo

## 📋 Visão Geral

O painel administrativo do DerivBot permite gerenciar licenças, configurar emails automáticos e integrar com sistemas de venda externos.

## 🚀 Acesso ao Admin

### URL de Acesso
```
http://localhost:5000/admin
```

**⚠️ Importante:** O admin só é acessível após fazer login no sistema principal.

## 🎯 Funcionalidades

### 📊 Dashboard
- **Estatísticas em tempo real:**
  - Total de licenças
  - Licenças ativas
  - Licenças expiradas
  - Licenças geradas hoje
- **Licenças recentes:** Lista das 5 licenças mais recentes

### ➕ Gerar Licença
- **Tipos disponíveis:**
  - Vitalício
  - Anual (365 dias)
  - Mensal (30 dias)
  - Teste (7 dias)
- **Campos:**
  - Email do cliente (opcional)
  - Nome do cliente (opcional)
  - Observações (opcional)
  - Envio automático de email (checkbox)

### 📋 Gerenciar Licenças
- **Visualizar todas as licenças**
- **Ações disponíveis:**
  - ✏️ Editar (em desenvolvimento)
  - 🗑️ Excluir
  - 📧 Reenviar email
- **Exportar para CSV**

### 📧 Configuração de Email
- **Configurações SMTP:**
  - Servidor SMTP (ex: smtp.gmail.com)
  - Porta (ex: 587)
  - Email de envio
  - Senha do app
- **Funcionalidades:**
  - Teste de configuração
  - Preview do template de email

### 🔌 API para Integração
- **Endpoint público para sistemas de venda**
- **Chave API para autenticação**
- **Documentação completa da API**

## 📧 Sistema de Email

### Configuração Recomendada (Gmail)
```
Servidor SMTP: smtp.gmail.com
Porta: 587
Email: seu@gmail.com
Senha: senha_do_app_google
```

### Template de Email
O sistema envia automaticamente um email profissional com:
- ✅ Código da licença destacado
- ✅ Instruções passo a passo
- ✅ Links diretos para obter tokens
- ✅ Dicas de segurança
- ✅ Informações de suporte

## 🔌 API Pública

### Endpoint para Gerar Licença
```http
POST /api/public/generate-license
Content-Type: application/json

{
    "api_key": "SUA_CHAVE_API",
    "tipo": "vitalicio",
    "email": "cliente@email.com",
    "nome": "Nome do Cliente",
    "observacoes": "Compra via sistema X",
    "enviar_email": true
}
```

### Resposta de Sucesso
```json
{
    "success": true,
    "codigo_licenca": "DERIVBOT-A1B2-C3D4",
    "message": "Licença gerada com sucesso",
    "email_enviado": true
}
```

### Códigos de Erro
- `401`: Chave API inválida
- `400`: Email obrigatório não fornecido
- `500`: Erro interno do servidor

## 🔐 Segurança

### Chave API
- Gerada automaticamente no primeiro acesso
- Pode ser regenerada a qualquer momento
- Necessária para usar a API pública

### Acesso Restrito
- Apenas usuários logados podem acessar o admin
- Senhas de email não são exibidas por segurança
- Logs detalhados de todas as operações

## 📁 Arquivos de Configuração

### `data/admin_config.json`
```json
{
    "email": {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "email_user": "seu@email.com",
        "email_pass": "senha_do_app"
    },
    "api_key": "chave_api_gerada_automaticamente"
}
```

### `data/licencas.json`
```json
{
    "licenca_001": {
        "codigo_licenca": "DERIVBOT-A1B2-C3D4",
        "status": "ativa",
        "plano": "vitalicio",
        "validade": "VITALICIO",
        "hwid": "",
        "ip": "",
        "deriv_real": "",
        "deriv_demo": "",
        "token_deriv_real": "",
        "token_deriv_demo": "",
        "data_criacao": "2024-06-05 14:30:00",
        "data_vinculacao": "",
        "cliente_email": "cliente@email.com",
        "cliente_nome": "Nome do Cliente",
        "observacoes": "Licença gerada via admin"
    }
}
```

## 🔄 Fluxo de Trabalho

### 1. Venda Manual
1. Cliente compra o produto
2. Acesse `/admin`
3. Vá em "Gerar Licença"
4. Preencha os dados do cliente
5. Marque "Enviar email automaticamente"
6. Clique em "Gerar Licença"
7. Cliente recebe email com instruções

### 2. Venda Automática (API)
1. Sistema de vendas faz POST para `/api/public/generate-license`
2. Licença é gerada automaticamente
3. Email é enviado automaticamente
4. Cliente recebe instruções por email

### 3. Ativação pelo Cliente
1. Cliente recebe email com código
2. Cliente executa `executar_derivbot.bat`
3. Cliente acessa tela de login
4. Cliente insere código + tokens da Deriv
5. Sistema valida e vincula dispositivo
6. Cliente pode usar o bot

## 🛠️ Manutenção

### Logs
- Todos os eventos são logados
- Geração de licenças
- Envios de email
- Erros e exceções

### Backup
- Faça backup regular de `data/licencas.json`
- Faça backup de `data/admin_config.json`

### Monitoramento
- Verifique estatísticas no dashboard
- Monitore licenças expiradas
- Acompanhe emails não enviados

## 🆘 Solução de Problemas

### Email não está sendo enviado
1. Verifique configurações SMTP
2. Use "Testar Email" no admin
3. Verifique se a senha do app está correta
4. Confirme que 2FA está ativado no Gmail

### API retorna erro 401
1. Verifique se a chave API está correta
2. Regenere a chave API se necessário
3. Confirme que está usando o endpoint correto

### Licença não está sendo criada
1. Verifique logs no terminal
2. Confirme que `data/` tem permissões de escrita
3. Verifique se há espaço em disco

## 📞 Suporte

Para suporte técnico ou dúvidas sobre o painel admin:
- 📧 Email: admin@derivbot.com
- 💬 WhatsApp: +55 11 99999-9999
- 🌐 Documentação: www.derivbot.com/docs

---

**🎉 O painel admin está pronto para gerenciar seu negócio de trading bots de forma profissional e automatizada!**
