@echo off
setlocal
cd /d "%~dp0"

title SleepKicker
echo Starting SleepKicker...
echo Project: %cd%

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Create it and install requirements first.
  echo   python -m venv .venv
  echo   .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)

if not exist ".env" (
  echo ERROR: .env not found. Copy .env.example to .env and set DISCORD_TOKEN.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" main.py
set EXITCODE=%ERRORLEVEL%

echo.
echo SleepKicker exited with code %EXITCODE%.
pause
exit /b %EXITCODE%
