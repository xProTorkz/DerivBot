@echo off
chcp 65001 > nul
title Deriv Bot - Sistema de Trading

echo ===================================
echo    Deriv Bot - Sistema de Trading
echo ===================================
echo.

:: Verifica se o Python está instalado
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo Por favor, instale o Python 3.8 ou superior.
    echo Visite: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Verifica se o pip está instalado
pip --version > nul 2>&1
if errorlevel 1 (
    echo [ERRO] pip nao encontrado!
    echo Por favor, reinstale o Python com pip.
    pause
    exit /b 1
)

:: Cria ambiente virtual se não existir
if not exist "venv" (
    echo [INFO] Criando ambiente virtual...
    python -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar ambiente virtual!
        pause
        exit /b 1
    )
)

:: Ativa o ambiente virtual
echo [INFO] Ativando ambiente virtual...
call venv\Scripts\activate.bat

:: Atualiza pip
echo [INFO] Atualizando pip...
python -m pip install --upgrade pip

:: Instala/atualiza dependências
echo [INFO] Instalando dependencias...
pip install --no-cache-dir -r requirements.txt

:: Inicia a aplicação
echo.
echo [INFO] Iniciando Deriv Bot...
echo [INFO] Acesse: http://localhost:5000
echo.
echo Pressione CTRL+C para encerrar
echo.

python main.py

:: Em caso de erro
if errorlevel 1 (
    echo.
    echo [ERRO] A aplicacao foi encerrada com erro!
    pause
)

:: Desativa o ambiente virtual
call venv\Scripts\deactivate.bat
