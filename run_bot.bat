@echo off
REM === Neon Runner - Telegram Bot runner ===
REM Uses .venv if present, else system python
cd /d "%~dp0"
title Neon Runner BOT ^(@dabi_plays_bot^)

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

if not exist ".env" (
  echo [ERROR] .env topilmadi! .env.example dan nusxa olib toldiring.
  echo   copy .env.example .env
  pause
  exit /b 1
)

echo [BOT] Python: %PY%
%PY% -c "import aiogram, dotenv; print('deps OK')" 2>nul
if errorlevel 1 (
  echo [BOT] Kutubxonalar topilmadi, urnatilmoqda...
  %PY% -m pip install --upgrade pip
  %PY% -m pip install -r requirements.txt
)

echo [BOT] Bot ishga tushmoqda... (python -m bot.bot)
echo [BOT] Tuxtatish uchun: Ctrl+C
%PY% -m bot.bot
pause
