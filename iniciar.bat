@echo off
rem Abre el rastreador en http://localhost:8000. Si es la primera vez en este PC, instala todo antes.
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  call "%~dp0instalar.bat" || exit /b 1
)
set PYTHONIOENCODING=utf-8
title Rastreador de ofertas - no cierres esta ventana
echo Rastreador en http://localhost:8000  (cierra esta ventana para apagarlo)
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8000"
".venv\Scripts\python.exe" -m uvicorn app.server:app --host 127.0.0.1 --port 8000
