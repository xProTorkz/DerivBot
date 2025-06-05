@echo off
title DerivBot - Sistema de Trading Automatizado
echo.
echo ========================================
echo    🚀 DERIVBOT - INICIANDO SISTEMA
echo ========================================
echo.
echo ⚙️  Iniciando servidor...
echo 🌐 Acesse: http://localhost:5000
echo 🔧 Admin: http://localhost:5000/admin
echo.
echo ⚠️  Para parar o sistema, pressione Ctrl+C
echo.

cd /d "%~dp0"
python src/main.py

pause
