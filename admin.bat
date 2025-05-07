@echo off
chcp 65001 > nul
title DerivBot - Gerenciador de Licenças

:menu
cls
echo ========================================================
echo        DerivBot - Sistema de Gerenciamento de Licenças
echo ========================================================
echo.
echo [1] Gerar Nova Licença
echo [2] Listar Licenças Existentes
echo [3] Verificar Licenças Expiradas
echo [4] Revogar uma Licença
echo [5] Atualizar uma Licença
echo [6] Sair
echo.
echo ========================================================
echo.

set /p opcao=Digite a opção desejada: 

if "%opcao%"=="1" goto gerar_licenca
if "%opcao%"=="2" goto listar_licencas
if "%opcao%"=="3" goto verificar_licencas
if "%opcao%"=="4" goto revogar_licenca
if "%opcao%"=="5" goto atualizar_licenca
if "%opcao%"=="6" goto sair

echo.
echo Opção inválida. Tente novamente.
timeout /t 2 > nul
goto menu

:gerar_licenca
call :verificar_ambiente
echo.
echo === GERADOR DE NOVA LICENÇA ===
echo.
set /p email=Digite o email do cliente: 
echo.
echo Planos disponíveis:
echo [1] FREE (7 dias)
echo [2] MENSAL (30 dias)
echo [3] VITALÍCIO
echo.
set /p plano_opcao=Selecione o plano: 

set plano=free
if "%plano_opcao%"=="1" set plano=free
if "%plano_opcao%"=="2" set plano=mensal
if "%plano_opcao%"=="3" set plano=vitalicio

set /p nome=Digite o nome do cliente (opcional): 

if "%nome%"=="" (
    python gerador_licencas.py criar -e "%email%" -p %plano%
) else (
    python gerador_licencas.py criar -e "%email%" -p %plano% -n "%nome%"
)

pause
goto menu

:listar_licencas
call :verificar_ambiente
echo.
echo === LISTAR LICENÇAS ===
echo.
echo [1] Todas as licenças
echo [2] Apenas licenças ativas
echo [3] Apenas licenças revogadas
echo [4] Apenas licenças expiradas
echo.
set /p filtro_opcao=Selecione o filtro: 

if "%filtro_opcao%"=="1" (
    python gerador_licencas.py listar
) else if "%filtro_opcao%"=="2" (
    python gerador_licencas.py listar -f ativa
) else if "%filtro_opcao%"=="3" (
    python gerador_licencas.py listar -f revogada
) else if "%filtro_opcao%"=="4" (
    python gerador_licencas.py listar -f expirada
) else (
    echo Opção inválida. Listando todas as licenças.
    python gerador_licencas.py listar
)

pause
goto menu

:verificar_licencas
call :verificar_ambiente
echo.
echo === VERIFICAR LICENÇAS EXPIRADAS ===
echo.
python gerador_licencas.py verificar
pause
goto menu

:revogar_licenca
call :verificar_ambiente
echo.
echo === REVOGAR LICENÇA ===
echo.
set /p codigo=Digite o código da licença a ser revogada: 
python gerador_licencas.py revogar -c "%codigo%"
pause
goto menu

:atualizar_licenca
call :verificar_ambiente
echo.
echo === ATUALIZAR LICENÇA ===
echo.
set /p codigo=Digite o código da licença a ser atualizada: 
echo.
echo Selecione o novo plano:
echo [1] FREE (7 dias)
echo [2] MENSAL (30 dias)
echo [3] VITALÍCIO
echo.
set /p plano_opcao=Selecione o novo plano: 

set plano=free
if "%plano_opcao%"=="1" set plano=free
if "%plano_opcao%"=="2" set plano=mensal
if "%plano_opcao%"=="3" set plano=vitalicio

python gerador_licencas.py atualizar -c "%codigo%" -p %plano%
pause
goto menu

:verificar_ambiente
:: Verifica se o Python está instalado
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo Por favor, instale o Python 3.8 ou superior.
    echo Visite: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Verifica se o ambiente virtual existe, caso contrário cria
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

:: Verifica se requirements.txt existe e instala dependências
if exist "requirements.txt" (
    echo [INFO] Instalando/atualizando dependencias...
    pip install --no-cache-dir -r requirements.txt > nul
)
exit /b 0

:sair
echo.
echo Encerrando o sistema...
timeout /t 2 > nul
exit /b 0 