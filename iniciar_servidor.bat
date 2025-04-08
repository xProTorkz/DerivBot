@echo off
echo Iniciando servidor Flask...

:: Ativa o ambiente virtual
call venv\Scripts\activate

:: Inicia o app com o Python certo
python app.py

pause
