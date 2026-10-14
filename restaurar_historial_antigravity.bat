@echo off
title Restaurador y Reiniciador de Historial - Antigravity IDE
cls
echo ===================================================================
echo     ANTIGRAVITY CHAT GUARDIAN - REINICIAR Y RESTAURAR CHATS
echo ===================================================================
echo.
cd /d "%~dp0"
python src\recovery\restart_and_restore.py

echo.
timeout /t 3 >nul
exit
