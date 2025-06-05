@echo off
chcp 65001 >nul
title DerivBot - Sistema de Trading Automatizado

echo.
echo ================================================================================
echo                          DERIVBOT - TRADING BOT
echo                     Sistema de Trading Automatizado
echo ================================================================================
echo.

:: Verifica se o Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRO: Python nao encontrado!
    echo.
    echo Por favor, instale o Python 3.8 ou superior:
    echo    https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Verifica se esta no diretorio correto
if not exist "src\main.py" (
    echo ERRO: Arquivo principal nao encontrado!
    echo.
    echo Certifique-se de que esta executando este arquivo na pasta raiz do DerivBot
    echo    Estrutura esperada:
    echo    DerivBot\
    echo    src\
    echo       main.py
    echo       config\
    echo    templates\
    echo    static\
    echo    executar_derivbot.bat
    echo.
    pause
    exit /b 1
)

:: Verifica se o ambiente virtual existe
if not exist "venv\" (
    echo Criando ambiente virtual...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ERRO: Falha ao criar ambiente virtual!
        pause
        exit /b 1
    )
    echo Ambiente virtual criado com sucesso!
)

:: Ativa o ambiente virtual
echo Ativando ambiente virtual...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERRO: Falha ao ativar ambiente virtual!
    pause
    exit /b 1
)

:: Verifica se requirements.txt existe e instala dependencias
if exist "requirements.txt" (
    echo Verificando dependencias...
    pip install -r requirements.txt --quiet
    if %errorlevel% neq 0 (
        echo Algumas dependencias podem nao ter sido instaladas corretamente
        echo    Continuando mesmo assim...
    ) else (
        echo Dependencias verificadas!
    )
) else (
    echo Arquivo requirements.txt nao encontrado
    echo    Instalando dependencias basicas...
    pip install flask websocket-client requests python-dotenv --quiet
)

:: Cria diretorios necessarios se nao existirem
if not exist "data\" mkdir data
if not exist "logs\" mkdir logs

echo.
echo Iniciando DerivBot...
echo.
echo Painel de controle estara disponivel em:
echo    http://localhost:5000
echo    http://127.0.0.1:5000
echo.
echo Para parar o sistema, pressione Ctrl+C
echo.
echo ===============================================================================
echo.

:: Inicia o aplicativo
cd src
python main.py

:: Se chegou ate aqui, o programa foi encerrado
echo.
echo ===============================================================================
echo.
echo DerivBot foi encerrado.
echo.

:: Desativa o ambiente virtual
deactivate

echo Pressione qualquer tecla para fechar esta janela...
pause >nul
