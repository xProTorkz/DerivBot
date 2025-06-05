# DerivBot - Trading Bot MVP

Bot de trading automatizado para Deriv com sistema completo de gestão de riscos e stops.

## 🚀 Funcionalidades

### ✅ Sistema de Trading
- **Estratégia Scalping**: Contratos de 15 segundos em VIX75/VIX100
- **Indicadores Técnicos**: EMA(8/21), RSI(14), Bollinger Bands(20,2)
- **3 Modos de Operação**: Iniciante, Conservador, Agressivo
- **Operações Simultâneas**: 3-10 operações baseado no modo

### ✅ Sistema de Stops Avançado
- **Stop Loss por Operação**: 1.5-3% baseado no modo
- **Take Profit por Operação**: 3-6% baseado no modo
- **Stop Loss Global**: 5-15% do saldo total
- **Take Profit Global**: 10-25% do saldo total
- **Trailing Stop**: Ativo nos modos conservador/agressivo

### ✅ Gestão de Riscos
- **Validação Pré-Operação**: Antes de cada entrada
- **Monitoramento 24/7**: Métricas em tempo real
- **Alertas Automáticos**: Quando limites são atingidos
- **Proteção do Capital**: Stops automáticos

### ✅ Interface Moderna
- **Logs em Tempo Real**: Categorizados por cores
- **Métricas Visuais**: Win rate, drawdown, operações
- **Fonte Courier New**: Nos resultados financeiros
- **Responsiva**: Desktop e mobile

## 📁 Estrutura do Projeto

```
DerivBot/
├── main.py                    # Servidor Flask principal
├── requirements.txt           # Dependências Python
├── src/
│   ├── core/
│   │   ├── motor.py          # Motor de trading + Sistema de Stops
│   │   ├── catalogador.py    # Análise técnica e sinais
│   │   └── inteligencia.py   # IA para decisões de trading
│   ├── config/
│   │   └── config.py         # Configurações globais
│   └── utils/
│       ├── logger_unificado.py    # Sistema de logs
│       └── reconexao_unificada.py # Reconexão automática
├── static/
│   ├── scripts.js            # JavaScript principal
│   ├── mobile.js             # Funcionalidades mobile
│   ├── style.css             # Estilos principais
│   └── mobile.css            # Estilos mobile
├── templates/
│   └── painel.html           # Interface web principal
└── data/
    ├── licencas.json         # Sistema de licenças
    └── admin_licencas.json   # Licenças administrativas
```

## 🛠️ Instalação

### Pré-requisitos
- Python 3.8+
- Conta na Deriv (demo ou real)
- Token de API da Deriv

### Passos
1. **Clone o repositório**
   ```bash
   git clone <repository-url>
   cd DerivBot
   ```

2. **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

3. **Execute o sistema**
   ```bash
   python main.py
   ```

4. **Acesse a interface**
   ```
   http://localhost:5000
   ```

## 🎯 Como Usar

### 1. Configuração Inicial
- Insira seu token da Deriv na interface
- Selecione conta Demo para testes
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

## 🆘 Suporte

Para suporte técnico ou dúvidas:
1. Verifique os logs em tempo real
2. Consulte a documentação da API Deriv
3. Use sempre conta demo para testes

---

**⚡ Sistema MVP Completo - Pronto para Produção! ⚡**
