@echo off
REM =====================================
REM DerivBot - Script de inicialização para Windows
REM =====================================

echo.
echo ===================================
echo    DerivBot - Inicializando...
echo ===================================
echo.

REM Verifica se o Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado. Por favor, instale o Python 3.8 ou superior.
    echo Voce pode baixar em: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Verifica se o ambiente virtual existe
if not exist venv (
    echo [INFO] Criando ambiente virtual...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao criar ambiente virtual.
        pause
        exit /b 1
    )
)

REM Ativa o ambiente virtual
echo [INFO] Ativando ambiente virtual...
call venv\Scripts\activate.bat

REM Instala as dependências
echo [INFO] Verificando dependencias...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [AVISO] Algumas dependencias podem nao ter sido instaladas corretamente.
)

REM Verifica se o arquivo .env existe
if not exist .env (
    echo [INFO] Criando arquivo .env...
    echo SECRET_KEY=DerivBotSecretKey123 > .env
)

REM Cria diretório de dados se não existir
if not exist data (
    echo [INFO] Criando diretorio de dados...
    mkdir data
)

REM Inicia o servidor
echo.
echo [INFO] Iniciando o DerivBot...
echo [INFO] Acesse o painel em: http://localhost:5000
echo [INFO] Pressione Ctrl+C para encerrar o servidor
echo.
python main.py

REM Desativa o ambiente virtual ao sair
call venv\Scripts\deactivate.bat

pause
