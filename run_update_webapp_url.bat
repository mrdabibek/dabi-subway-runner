@echo off
REM === Neon Runner - cloudflared tunnel URL ni .env ga avtomatik yozish ===
REM Ishlatish: run_update_webapp_url.bat https://xxx.trycloudflare.com
cd /d "%~dp0"

if "%~1"=="" (
  echo Ishlatish:
  echo   run_update_webapp_url.bat https://xxx.trycloudflare.com
  echo.
  echo TUNNEL oynasidagi 'https://....trycloudflare.com' manzilini argument qilib bering.
  pause
  exit /b 1
)

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo [*] .env zaxiralanmoqda -^> .env.bak
copy /y .env .env.bak >nul

%PY% update_webapp_url.py "%~1"
if errorlevel 1 exit /b 1
echo.
echo [OK] Tayyor! API va BOT ni restart qiling (run_all.bat ni qayta ishga tushiring).
pause
