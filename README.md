# DerivBot - Sistema de Trading Automatizado

Um sistema avançado de trading automatizado para a plataforma Deriv, desenvolvido em Python com interface web moderna.

## 🚀 Características Principais

- **Interface Web Moderna**: Painel de controle intuitivo e responsivo
- **Trading Automatizado**: Estratégias de scalping otimizadas
- **Múltiplos Modos**: Iniciante, Conservador e Agressivo
- **Gestão de Risco**: Stop loss, take profit e martingale controlado
- **Logs em Tempo Real**: Monitoramento completo das operações
- **Sistema de Licenças**: Controle de acesso seguro

## 📋 Requisitos

- Python 3.8 ou superior
- Conta na Deriv (demo ou real)
- Token de API da Deriv
- Windows 10/11 (recomendado)

## 🔧 Instalação e Execução

### Método Simples (Recomendado)

1. **Baixe o projeto** e extraia para uma pasta
2. **Execute o arquivo .bat**:
   ```
   📁 Clique duas vezes em: executar_derivbot.bat
   ```
3. **Aguarde a instalação automática** das dependências
4. **Acesse o painel** em: http://localhost:5000

### Método Manual

1. **Clone o repositório**:

   ```bash
   git clone https://github.com/seu-usuario/derivbot.git
   cd derivbot
   ```

2. **Crie ambiente virtual**:

   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```

3. **Instale dependências**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Execute o sistema**:
   ```bash
   cd src
   python main.py
   ```

## 📁 Nova Estrutura do Projeto

```
derivbot/
├── 📄 executar_derivbot.bat        # Executar sistema (PRINCIPAL)
├── 📄 executar_desenvolvimento.bat # Executar em modo dev
├── 📄 requirements.txt             # Dependências Python
├── 📂 src/                         # Código fonte
│   ├── 📄 main.py                  # Arquivo principal (MOVIDO)
│   ├── 📂 config/                  # Configurações
│   │   ├── 📄 .env                 # Variáveis de ambiente (MOVIDO)
│   │   └── 📄 config.py            # Configurações do sistema
│   ├── 📂 core/                    # Lógica principal
│   │   ├── 📄 motor.py             # Motor de trading
│   │   ├── 📄 catalogador.py       # Catalogador de operações
│   │   └── 📄 inteligencia.py      # Sistema inteligente
│   └── 📂 utils/                   # Utilitários
│       ├── 📄 gerador_licencas.py  # Sistema de licenças
│       ├── 📄 logger_unificado.py  # Sistema de logs
│       └── 📄 reconexao_unificada.py # Sistema de reconexão
├── 📂 templates/                   # Templates HTML
│   └── 📄 painel.html              # Interface principal
├── 📂 static/                      # Arquivos estáticos (CSS, JS)
├── 📂 data/                        # Dados e configurações
└── 📂 logs/                        # Arquivos de log
```

## 🎯 Como Usar

### 1. Configuração Inicial

- Execute `executar_derivbot.bat`
- Faça login no painel com suas credenciais
- Configure o modo de operação desejado

### 2. Modos de Operação

#### **Iniciante** 🟢

- Stop Loss: 1.5% por operação / 5% global
- Take Profit: 3% por operação / 10% global
- Meta máxima: $20
- Operações simultâneas: 3

#### **Conservador** 🟡

- Stop Loss: 2% por operação / 8% global
- Take Profit: 4% por operação / 15% global
- Meta máxima: $50
- Operações simultâneas: 5
- Trailing Stop ativo

#### **Agressivo** 🔴

- Stop Loss: 3% por operação / 15% global
- Take Profit: 6% por operação / 25% global
- Meta máxima: $100+
- Operações simultâneas: 10
- Trailing Stop ativo

### 3. Monitoramento

- **Logs em Tempo Real**: Acompanhe todas as ações
- **Gestão de Riscos**: Expandível na aba "Histórico Completo"
- **Métricas**: Win rate, drawdown, operações simultâneas
- **Alertas**: Notificações quando stops são atingidos

## 🔧 APIs Disponíveis

### Sistema de Stops

- `GET /api/stops/status` - Status dos stops ativos
- `POST /api/stops/configurar` - Configura stops por modo

### Gestão de Riscos

- `GET /api/riscos/metricas` - Métricas em tempo real
- `GET /api/riscos/alertas` - Alertas ativos
- `POST /api/riscos/validar` - Validação pré-operação

### Sistema Geral

- `GET /api/performance` - Performance financeira
- `GET /api/logs` - Logs categorizados

## 🧪 Testes

O sistema inclui botões de simulação para testar:

- **+$15, -$8, +$22**: Simula operações
- **Reset**: Limpa histórico e lucro
- **Conta Demo**: Sempre use para testes

## ⚠️ Avisos Importantes

1. **Use sempre conta DEMO** para testes
2. **Nunca invista** mais do que pode perder
3. **Monitore sempre** as operações
4. **Respeite os stops** configurados
5. **Trading envolve riscos** - use com responsabilidade

## 📊 Tecnologias

- **Backend**: Python, Flask, WebSocket
- **Frontend**: HTML5, CSS3, JavaScript
- **APIs**: Deriv WebSocket API
- **Análise**: NumPy, Pandas, TA-Lib
- **Logs**: Sistema unificado thread-safe

## 📄 Licença

MIT License - Veja LICENSE para detalhes.

## 🚀 Execução Rápida

### Para Usuários Finais

1. 📁 Baixe e extraia o projeto
2. 🖱️ Clique duas vezes em `executar_derivbot.bat`
3. 🌐 Acesse http://localhost:5000
4. 🎯 Configure e inicie o trading

### Para Desenvolvedores

1. 🖱️ Clique duas vezes em `executar_desenvolvimento.bat`
2. 🔧 Modo debug ativo com auto-reload
3. 📝 Logs detalhados habilitados
4. 🔄 Mudanças no código são aplicadas automaticamente

### Configurações de Ambiente

O arquivo `src/config/.env` contém:

```env
# Configurações essenciais do DerivBot
SECRET_KEY=chave_secreta_gerada_automaticamente
DEEPSEEK_API_KEY=sk-d4f5f8438bb9483897d9d664bf2ee020
FLASK_ENV=development
DEBUG=False
```

## 🚨 Avisos Importantes

⚠️ **ATENÇÃO**: Trading envolve riscos. Nunca invista mais do que pode perder.

⚠️ **DEMO FIRST**: Sempre teste em conta demo antes de usar conta real.

⚠️ **RESPONSABILIDADE**: O usuário é responsável por suas operações e resultados.

## 📞 Suporte

- **WhatsApp**: +55 11 99999-9999
- **Email**: suporte@derivbot.com
- **Documentação**: https://docs.derivbot.com

## 🤝 Contribuição

Contribuições são bem-vindas! Por favor, leia as diretrizes de contribuição antes de submeter pull requests.

---

**Desenvolvido com ❤️ para a comunidade de traders**
