@echo off
rem Barrido completo: todas las búsquedas y páginas (1 vez al día).
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -m app.scraper --modo completo >> "datos\barrido.log" 2>&1
