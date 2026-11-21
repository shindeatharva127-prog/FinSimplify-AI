@echo off
setlocal
cd /d "%~dp0"
title FinSimplify AI

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.11+ is required. Install it from https://www.python.org/downloads/ and tick "Add to PATH".
  pause
  exit /b 1
)

if not exist venv (
  echo Creating virtual environment...
  python -m venv venv
)
call venv\Scripts\activate.bat

echo Installing dependencies (first run may take a minute)...
pip install -q -r requirements.txt

if not exist .env (
  copy .env.example .env >nul
  echo.
  echo A .env file was created. Paste your NEWSAPI_KEY and GROQ_API_KEY, save, then close Notepad.
  notepad .env
)

echo Starting FinSimplify AI at http://localhost:8000 ...
start "" /b cmd /c "timeout /t 4 >nul & (start chrome http://localhost:8000 || start http://localhost:8000)"
uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
