@echo off
title Detener Vigilante de Antigravity
cls
echo ========================================================
echo   DETENIENDO VIGILANTE EN SEGUNDO PLANO...
echo ========================================================
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*cli.py watch*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host ('[V] Vigilante PID ' + $_.ProcessId + ' detenido.') }"
timeout /t 2 /nobreak >nul
exit
