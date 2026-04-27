@echo off
setlocal
cd /d "%~dp0"

echo ================================
echo  J.A.R.V.I.S Google Full Control
echo ================================

if not exist .env (
    copy .env.example .env >nul
    echo Created .env file. Paste your Google AI Studio API key into it.
    notepad .env
)

if not exist .venv (
    echo Creating Python virtual environment...
    py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Starting server...
echo Open this in your browser: http://127.0.0.1:5050
echo.
start "" http://127.0.0.1:5050
python server.py
pause
