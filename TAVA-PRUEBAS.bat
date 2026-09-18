@echo off
chcp 65001 >nul
setlocal
title TAVA PRUEBAS LOCAL

cd /d "%~dp0"

echo.
echo ############################################################
echo #                                                          #
echo #   TAVA — ENTORNO DE PRUEBAS (SOLO EN TU PC)              #
echo #                                                          #
echo #   Usa base de datos LOCAL.                               #
echo #   NO escribe en Vercel ni en Render de produccion.       #
echo #                                                          #
echo ############################################################
echo.

call "%~dp0scripts\crear-acceso-escritorio-pruebas.bat" silent
if errorlevel 1 echo (No se pudo crear el icono del Escritorio; puedes seguir igual.)

echo.
echo En unos segundos se abrira http://localhost:4200
echo Busca arriba la cinta verde: PRUEBAS LOCAL
echo Admin demo: admin@tavateatro.com / AdminTava2026!
echo.
echo Para apagar Postgres: doble clic en TAVA-Detener-PRUEBAS.bat
echo.

REM Abrir el navegador cuando Angular ya haya tenido tiempo de levantar
start "TAVA abrir navegador" cmd /c "timeout /t 28 /nobreak >nul & start http://localhost:4200"

call "%~dp0iniciar-local.bat"
exit /b %ERRORLEVEL%
