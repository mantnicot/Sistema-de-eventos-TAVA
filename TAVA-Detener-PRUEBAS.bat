@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo Deteniendo PostgreSQL local (PRUEBAS)...
docker compose stop postgres

echo.
echo Cierra manualmente las ventanas "TAVA API" y "TAVA Web" si siguen abiertas.
echo Produccion (Vercel/Render) no se ve afectada.
echo.
pause
