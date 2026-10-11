@echo off
title Antigravity Chat Guardian - Setup
cls
echo ========================================================
echo        ANTIGRAVITY CHAT GUARDIAN - INSTALACION
echo ========================================================
echo.
echo [*] Verificando instalacion de Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python no fue encontrado en el PATH del sistema.
    echo     Por favor instala Python 3.10 o superior marcando "Add Python to PATH".
    pause
    exit /b 1
)

python --version
echo [V] Python detectado correctamente.
echo.

echo [*] Verificando entorno de Google Antigravity IDE...
python cli.py doctor

echo.
echo ========================================================
echo   Instalacion completada con exito.
echo ========================================================
echo.
echo Opciones disponibles:
echo   1. Restaurar historial ahora:  restaurar_historial_antigravity.bat
echo   2. Activar respaldo continuo:   iniciar_vigilante_silencioso.vbs
echo   3. Abrir visor web local:      run_hub.bat
echo.
pause
