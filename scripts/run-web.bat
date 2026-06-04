@echo off
cd /d "%~dp0..\frontend"
if not exist "node_modules\" (
    echo ERROR: Ejecuta primero iniciar-local.bat en la raiz del proyecto.
    pause
    exit /b 1
)
title TAVA Web - http://localhost:4200
echo Frontend TAVA en http://localhost:4200
echo.
call npm start
pause
