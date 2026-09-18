@echo off
REM Crea "TAVA PRUEBAS.lnk" en el Escritorio apuntando a TAVA-PRUEBAS.bat
setlocal
cd /d "%~dp0.."

set "TARGET=%cd%\TAVA-PRUEBAS.bat"
set "WORKDIR=%cd%"
set "LINK=%USERPROFILE%\Desktop\TAVA PRUEBAS.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$s = $ws.CreateShortcut('%LINK%'); " ^
  "$s.TargetPath = '%TARGET%'; " ^
  "$s.WorkingDirectory = '%WORKDIR%'; " ^
  "$s.WindowStyle = 1; " ^
  "$s.Description = 'TAVA entorno local de pruebas (no afecta produccion)'; " ^
  "$s.Save()"

if errorlevel 1 (
  echo No se pudo crear el acceso en el Escritorio.
  if /i not "%~1"=="silent" pause
  exit /b 1
)

echo Acceso creado: %LINK%
if /i not "%~1"=="silent" (
  echo.
  echo Doble clic en "TAVA PRUEBAS" del Escritorio para entrar en modo pruebas.
  pause
)
exit /b 0
