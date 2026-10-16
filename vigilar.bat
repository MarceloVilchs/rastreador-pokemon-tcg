@echo off
rem Pasada rápida: página 1 de las búsquedas de vigilancia. Envía alertas si hay bajas.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -m app.scraper --modo vigilancia >> "datos\vigilancia.log" 2>&1
