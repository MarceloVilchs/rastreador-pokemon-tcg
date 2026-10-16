@echo off
rem Abre la página del rastreador en http://localhost:8000
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
start "" http://localhost:8000
".venv\Scripts\python.exe" -m uvicorn app.server:app --host 127.0.0.1 --port 8000
