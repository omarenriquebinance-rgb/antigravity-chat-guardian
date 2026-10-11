@echo off
title Antigravity Live Backup Watcher
chcp 65001 >nul

echo ========================================================
echo   SERVICIO EN SEGUNDO PLANO: ANTIGRAVITY LIVE WATCHER
echo ========================================================
echo.
echo [*] Este servicio respalda de forma continua cualquier
echo     mensaje o chat nuevo emitido en Antigravity.
echo.

cd /d "%~dp0"
python cli.py watch

pause
