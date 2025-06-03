#!/bin/bash
# DerivBot - Script de inicialização para Linux

echo
echo "===== DerivBot - Inicializando ====="
echo

# Verifica se o Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "[ERRO] Python não encontrado. Por favor, instale o Python 3.8 ou superior."
    echo "Você pode instalar com: sudo apt-get install python3 python3-pip python3-venv"
    echo
    exit 1
fi

# Verifica a versão do Python
PYTHON_VERSION=$(python3 --version | grep -oP '(?<=Python )\d+\.\d+')
if (( $(echo "$PYTHON_VERSION < 3.8" | bc -l) )); then
    echo "[AVISO] Versão do Python pode não ser compatível. Recomendamos Python 3.8 ou superior."
    echo
    sleep 3
fi

# Verifica se o ambiente virtual existe, se não, cria
if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[ERRO] Falha ao criar ambiente virtual."
        exit 1
    fi
fi

# Ativa o ambiente virtual
echo "Ativando ambiente virtual..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "[ERRO] Falha ao ativar ambiente virtual."
    exit 1
fi

# Instala dependências se requirements.txt existir
if [ -f "requirements.txt" ]; then
    echo "Verificando dependências..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[AVISO] Algumas dependências podem não ter sido instaladas corretamente."
        sleep 3
    fi
else
    echo "Instalando dependências básicas..."
    pip install flask websocket-client python-dotenv numpy requests
fi

# Verifica se o arquivo .env existe, se não, cria um modelo
if [ ! -f ".env" ]; then
    echo "Criando arquivo .env de exemplo..."
    echo "# Configurações do DerivBot" > .env
    echo "FLASK_SECRET_KEY=chave_secreta_gerada_automaticamente" >> .env
    echo "DERIV_TOKEN_REAL=" >> .env
    echo "DERIV_TOKEN_DEMO=" >> .env
    echo "API_ID=71203" >> .env
    echo
    echo "[AVISO] Arquivo .env criado. Por favor, configure seus tokens da Deriv."
    sleep 3
fi

# Cria diretórios necessários se não existirem
mkdir -p data memoria logs

# Inicia o servidor Flask
echo
echo "===== DerivBot - Iniciando servidor ====="
echo
echo "Acesse o painel em: http://localhost:5000"
echo
echo "Pressione CTRL+C para encerrar o servidor"
echo

# Inicia o servidor Flask
python3 main.py

# Desativa o ambiente virtual ao sair
deactivate

echo
echo "===== DerivBot - Servidor encerrado ====="
echo
