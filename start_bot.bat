@echo off
setlocal
cd /d "%~dp0"

title SleepKicker
echo Starting SleepKicker...
echo Project: %cd%

if not exist ".env" (
  echo ERROR: .env not found. Copy .env.example to .env and set DISCORD_TOKEN.
  pause
  exit /b 1
)

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"
if not defined PYTHON_EXE (
  where py >nul 2>&1 && set "PYTHON_EXE=py -3"
)
if not defined PYTHON_EXE (
  where python >nul 2>&1 && set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
  echo ERROR: Python not found.
  echo Install Python 3.11+ or create a venv, then: pip install -r requirements.txt
  pause
  exit /b 1
)

echo Using: %PYTHON_EXE%
%PYTHON_EXE% main.py
set EXITCODE=%ERRORLEVEL%

echo.
echo SleepKicker exited with code %EXITCODE%.
pause
exit /b %EXITCODE%
