@echo off
title Asistente para Subir a GitHub - Antigravity Chat Guardian
cls
echo ========================================================
echo   SUBIR ANTIGRAVITY CHAT GUARDIAN A TU GITHUB
echo ========================================================
echo.
echo Paso 1: Ve a https://github.com/new en tu navegador.
echo Paso 2: Ponle de nombre al repositorio: antigravity-chat-guardian
echo         (Dejalo publico y NO marques agregar README ni .gitignore)
echo Paso 3: Haz clic en el boton verde "Create repository".
echo.
echo ========================================================
echo.
set /p REPO_URL="Pega aqui la URL de tu repositorio de GitHub: "

if "%REPO_URL%"=="" (
    echo [X] No ingresaste ninguna URL. Operacion cancelada.
    pause
    exit /b 1
)

echo.
echo [*] Configurando repositorio remoto...
git remote remove origin >nul 2>&1
git remote add origin %REPO_URL%
git branch -M main

echo [*] Subiendo proyecto a GitHub...
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo   [V] EXITO TOTAL: Tu proyecto ya esta publicado en GitHub!
    echo ========================================================
) else (
    echo.
    echo [!] Si te pidio credenciales o dio error, verifica que hayas iniciado
    echo     sesion en GitHub o tengas tu Personal Access Token configurado.
)

echo.
pause
