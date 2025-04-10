@echo off
title Iniciando Bot Deriv...
cd /d "%~dp0"

start /B python main.py
timeout /t 2 >nul
start http://127.0.0.1:5000
