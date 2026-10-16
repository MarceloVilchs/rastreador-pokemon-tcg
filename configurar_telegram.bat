@echo off
rem Configura (o reconfigura) las alertas por Telegram.
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set "TOKEN="
set /p "TOKEN=Pega el token de BotFather (Enter para usar el de notificaciones.json): "
echo Abre tu bot en Telegram, toca Iniciar y escríbele "hola" (tienes 2 minutos)...
if "%TOKEN%"=="" (
  ".venv\Scripts\python.exe" -m app.configurar_telegram
) else (
  ".venv\Scripts\python.exe" -m app.configurar_telegram --token "%TOKEN%"
)
set "TOKEN="
pause
