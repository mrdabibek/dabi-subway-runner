@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)
if not exist ".env" (
  echo [ERROR] .env topilmadi. .env.example dan nusxa olib toldiring.
  pause
  exit /b 1
)
%PY% -c "import fastapi, uvicorn, aiogram, httpx, dotenv" 2>nul
if errorlevel 1 (
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 exit /b 1
)
%PY% launcher.py
if errorlevel 1 pause
