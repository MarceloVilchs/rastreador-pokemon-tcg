@echo off
rem ============================================================
rem  Instalador del Rastreador de ofertas (Pokémon TCG + Switch 2)
rem  Doble clic. Se puede volver a ejecutar sin problema.
rem ============================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Instalando Rastreador de ofertas
echo.
echo  === Rastreador de ofertas: instalación ===
echo.

rem --- 1. Python 3.10 o superior ---
set "PY="
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY=python"
if not defined PY py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY=py -3"
if defined PY goto :python_ok
echo  [!] No encontré Python 3.10 o superior.
set "R="
set /p "R=     ¿Lo instalo ahora con winget? (S/N): "
if /i not "%R%"=="S" goto :sin_python
winget install -e --id Python.Python.3.13 --scope user --accept-package-agreements
echo.
echo  Python instalado. CIERRA esta ventana y vuelve a abrir instalar.bat.
pause
exit /b 1
:sin_python
echo  Descárgalo de https://www.python.org/downloads/ (marca "Add python.exe to PATH")
echo  y vuelve a abrir instalar.bat.
pause
exit /b 1
:python_ok
for /f "delims=" %%v in ('%PY% --version') do echo  [ok] %%v

rem --- 2. Entorno virtual y librerías ---
if exist ".venv\Scripts\python.exe" goto :venv_ok
echo  [..] Creando entorno de Python (.venv)...
%PY% -m venv .venv || goto :error
:venv_ok
echo  [..] Instalando librerías (puede tardar un par de minutos)...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip || goto :error
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt || goto :error
echo  [ok] Librerías instaladas
echo  [..] Instalando navegador Chromium para el scraper...
".venv\Scripts\python.exe" -m playwright install chromium || goto :error
echo  [ok] Chromium listo
if not exist datos mkdir datos

rem --- 3. Alertas por Telegram ---
echo.
if exist notificaciones.json (
  echo  [ok] notificaciones.json ya existe ^(alertas configuradas^)
  goto :tareas
)
echo  Alertas al celular por Telegram:
echo    - Si ya tienes tu bot, pega aquí su token de BotFather.
echo    - Si copiaste notificaciones.json de otro PC, cierra esto, pégalo en esta carpeta y vuelve a abrir.
echo    - Enter para omitir ^(puedes hacerlo después con configurar_telegram.bat^).
set "TOKEN="
set /p "TOKEN=     Token: "
if "%TOKEN%"=="" (
  copy /y notificaciones.ejemplo.json notificaciones.json >nul
  echo  [--] Telegram omitido por ahora
  goto :tareas
)
echo  Abre tu bot en Telegram, toca Iniciar y escríbele "hola" ^(tienes 2 minutos^)...
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -m app.configurar_telegram --token "%TOKEN%"
set "TOKEN="

rem --- 4. Tareas automáticas ---
:tareas
echo.
echo  Tareas automáticas: vigilancia cada 30 min (07:00-23:59) y barrido completo diario a las 08:00.
echo  OJO: actívalas en UN solo PC, si no te llegarán alertas duplicadas.
set "R="
set /p "R=     ¿Programarlas en este PC? (S/N): "
if /i "%R%"=="S" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0programar_tareas.ps1"

rem --- 5. Primer barrido ---
if exist "datos\precios.db" goto :fin
echo.
set "R="
set /p "R=     ¿Hago el primer barrido ahora para llenar la página? Tarda ~6 min (S/N): "
if /i not "%R%"=="S" goto :fin
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -u -m app.scraper --modo completo

:fin
echo.
echo  === Listo. Abre el rastreador con doble clic en iniciar.bat ===
echo.
pause
exit /b 0

:error
echo.
echo  [X] Algo falló en la instalación. Revisa el mensaje de arriba (¿hay internet?) y vuelve a intentar.
pause
exit /b 1
