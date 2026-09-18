@echo off
cd /d "%~dp0..\backend"
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Ejecuta primero iniciar-local.bat en la raiz del proyecto.
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"
set "PYTHONPATH=%~dp0..\backend\src"
title TAVA API PRUEBAS - http://localhost:8000/docs
echo API TAVA PRUEBAS LOCAL en http://localhost:8000
echo Swagger: http://localhost:8000/docs
echo (Postgres Docker local — no toca produccion)
echo.
uvicorn tava.main:app --reload --host 0.0.0.0 --port 8000
pause
