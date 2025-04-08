@echo off
echo Iniciando servidor Flask...

REM Ativar o ambiente virtual, se estiver usando (remova se não for o caso)
call venv\Scripts\activate

REM Iniciar o app Flask
start /B cmd /c "python app.py"

REM Espera 3 segundos pro servidor subir
timeout /t 3 >nul

REM Abre o navegador padrão na URL do painel
start http://localhost:5000

exit
