@echo off
REM === Neon Runner - Backend API runner (FastAPI + Uvicorn) ===
cd /d "%~dp0"
title Neon Runner API :8000

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

if not exist ".env" (
  echo [ERROR] .env topilmadi! .env.example dan nusxa olib toldiring.
  pause
  exit /b 1
)

echo [API] Python: %PY%
%PY% -c "import fastapi, uvicorn; print('deps OK')" 2>nul
if errorlevel 1 (
  echo [API] Kutubxonalar urnatilmoqda...
  %PY% -m pip install --upgrade pip
  %PY% -m pip install -r requirements.txt
)

echo [API] http://127.0.0.1:8000 ^| docs: http://127.0.0.1:8000/docs ^| health: http://127.0.0.1:8000/health
echo [API] WebApp ham shu portda: http://127.0.0.1:8000/webapp/
echo [API] Tuxtatish: Ctrl+C
%PY% -c "from api.main import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8000)"
pause
