@echo off
title Restaurador y Reiniciador de Historial - Antigravity IDE
cls
echo ===================================================================
echo     ANTIGRAVITY CHAT GUARDIAN - REINICIAR Y RESTAURAR CHATS
echo ===================================================================
echo.
cd /d "d:\ARREGLO-ANTIGAVITY"
python src\recovery\restart_and_restore.py

echo.
echo Presione cualquier tecla si la ventana no se cierra automaticamente...
timeout /t 3 >nul
exit
