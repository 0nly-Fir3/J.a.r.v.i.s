@echo off
setlocal
cd /d "%~dp0"
title JARVIS V10 - Personal OS Layer - OpenRouter

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env. Paste your OpenRouter key into it, save, then close Notepad.
  notepad ".env"
)

set "PYTHON_CMD="
py -3.12 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.12"
if "%PYTHON_CMD%"=="" py -3.11 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.11"
if "%PYTHON_CMD%"=="" py -3.10 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3.10"
if "%PYTHON_CMD%"=="" py -3 -c "import sys" >nul 2>nul && set "PYTHON_CMD=py -3"
if "%PYTHON_CMD%"=="" set "PYTHON_CMD=python"

echo Using Python command: %PYTHON_CMD%

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PYTHON_CMD% -m venv ".venv"
)

if exist ".venv\Scripts\python.exe" (
  call ".venv\Scripts\activate.bat"
) else (
  echo Failed to create virtual environment. Continuing with your normal Python install.
)

echo Python details:
python -c "import sys; print(sys.executable); print(sys.version)"

python -m pip install --upgrade pip setuptools wheel

echo.
echo Installing required packages...
python -m pip install -r "requirements_core.txt"
if errorlevel 1 (
  echo.
  echo Required package install failed. If you are using Python 3.14 and this keeps failing, install Python 3.12 and rerun this file.
  pause
  exit /b 1
)

echo.
echo Installing optional voice/OCR packages. These are allowed to fail.
python -m pip install edge-tts || echo edge-tts failed, continuing.
python -m pip install pytesseract || echo pytesseract failed, continuing.
python -m pip install pywin32 || echo pywin32 failed, continuing.
python -m pip install pywinauto || echo pywinauto failed, continuing.

echo.
echo Starting JARVIS V10 on http://127.0.0.1:5050
echo Keep this window open.
echo.
start "" http://127.0.0.1:5050
python server.py
pause
