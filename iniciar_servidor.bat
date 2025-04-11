@echo off
title Iniciando Bot Deriv...
cd /d "%~dp0"

:: Inicia o servidor Python em background
start /B python main.py

:: Aguarda 2 segundos pra garantir que o servidor subiu
timeout /t 2 >nul

start http://192.168.1.18:5000
