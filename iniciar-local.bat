@echo off
setlocal
title TAVA - Inicio local

REM Ir a la carpeta del proyecto (donde esta este .bat)
cd /d "%~dp0"

echo.
echo ========================================
echo   TAVA Teatro - Entorno local
echo ========================================
echo.

REM --- .env ---
if not exist ".env" (
    echo [1/5] Creando .env desde .env.example...
    copy /Y ".env.example" ".env" >nul
) else (
    echo [1/5] .env encontrado.
)

REM --- Docker / PostgreSQL ---
echo [2/5] Iniciando PostgreSQL (Docker)...
where docker >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Docker no esta instalado o no esta en el PATH.
    echo Instala Docker Desktop y vuelve a ejecutar este archivo.
    echo.
    goto :fin_error
)

docker compose up -d postgres
if errorlevel 1 (
    echo.
    echo ERROR: No se pudo iniciar PostgreSQL.
    echo Abre Docker Desktop y espera a que este en ejecucion.
    echo.
    goto :fin_error
)

echo       Esperando PostgreSQL (10 seg)...
timeout /t 10 /nobreak >nul

REM --- Backend ---
echo [3/5] Preparando backend Python...
cd /d "%~dp0backend"
if errorlevel 1 goto :fin_error

if not exist ".venv\Scripts\activate.bat" (
    echo       Creando entorno virtual...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: Python no encontrado. Instala Python 3.12 o superior.
        echo.
        goto :fin_error
    )
)

call ".venv\Scripts\activate.bat"
pip install -r requirements.txt -q
set "PYTHONPATH=%~dp0backend\src"

echo       Ejecutando seed...
python "%~dp0backend\scripts\seed.py"
if errorlevel 1 echo       Aviso: seed fallo (puede ser normal si ya hay datos).

REM --- Frontend ---
echo [4/5] Preparando frontend Angular...
cd /d "%~dp0frontend"
if errorlevel 1 goto :fin_error

if not exist "node_modules\" (
    echo       Instalando npm (primera vez, puede tardar varios minutos)...
    call npm install --legacy-peer-deps
    if errorlevel 1 (
        echo.
        echo ERROR: npm install fallo. Instala Node.js 20 o superior.
        echo.
        goto :fin_error
    )
)

REM --- Abrir API y Web en ventanas nuevas ---
echo [5/5] Abriendo API y frontend...
cd /d "%~dp0"

start "TAVA API" cmd /k call "%~dp0scripts\run-api.bat"
timeout /t 2 /nobreak >nul
start "TAVA Web" cmd /k call "%~dp0scripts\run-web.bat"

echo.
echo ========================================
echo   TAVA en ejecucion
echo ========================================
echo   Web:     http://localhost:4200
echo   API:     http://localhost:8000
echo   Swagger: http://localhost:8000/docs
echo   Admin:   admin@tavateatro.com / AdminTava2026!
echo.
echo   Cierra las ventanas TAVA API y TAVA Web para detener.
echo   PostgreSQL: docker compose stop postgres
echo ========================================
echo.
goto :fin_ok

:fin_error
echo Presiona una tecla para cerrar...
pause >nul
exit /b 1

:fin_ok
echo Presiona una tecla para cerrar esta ventana (API y Web siguen abiertas)...
pause >nul
exit /b 0
