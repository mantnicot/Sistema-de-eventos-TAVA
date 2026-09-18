@echo off
cd /d "%~dp0..\frontend"
if not exist "node_modules\" (
    echo ERROR: Ejecuta primero iniciar-local.bat en la raiz del proyecto.
    pause
    exit /b 1
)
title TAVA Web PRUEBAS - http://localhost:4200
echo Frontend TAVA PRUEBAS LOCAL en http://localhost:4200
echo (API local — no toca produccion)
echo.
call npm run start:local
pause
