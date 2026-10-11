@echo off
title Antigravity Chat Hub y Visor
cls
echo ========================================================
echo   CENTRO DE CONTROL Y VISOR DE CONVERSACIONES
echo ========================================================
echo.
cd /d "%~dp0"
echo [*] Sincronizando conversaciones recientes...
python cli.py sync
echo [*] Abriendo visor en el navegador (http://127.0.0.1:7890)...
start http://127.0.0.1:7890
echo.
echo Servidor activo. Presione Ctrl+C para salir.
python cli.py serve --port 7890
pause
