@echo off
title Restaurador de Historial Antigravity
cls
echo ========================================================
echo   RESTAURANDO HISTORIAL EN ANTIGRAVITY IDE...
echo ========================================================
taskkill /IM "Antigravity IDE.exe" /F >nul 2>&1
taskkill /IM "antigravity ide.exe" /F >nul 2>&1
timeout /t 2 /nobreak >nul

cd /d "%~dp0"
python cli.py restore-all --force

echo [*] Reabriendo Antigravity IDE de forma totalmente independiente...
powershell -NoProfile -Command "Start-Process -FilePath \"$env:LOCALAPPDATA\Programs\Antigravity IDE\Antigravity IDE.exe\""

timeout /t 1 /nobreak >nul
exit
