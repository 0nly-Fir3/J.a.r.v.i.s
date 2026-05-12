@echo off
setlocal
cd /d "%~dp0"
title JARVIS V10 - OpenRouter
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
start "" http://127.0.0.1:5050
python server.py
pause
