@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Deteniendo PostgreSQL (Docker)...
docker compose stop postgres

echo.
echo Las ventanas de API y Angular deben cerrarse manualmente
echo (cierra "TAVA API" y "TAVA Web" si siguen abiertas).
echo.
pause
