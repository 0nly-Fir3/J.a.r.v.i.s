@echo off
title JARVIS PC Controller v2 - Install Requirements
cd /d "%~dp0"
echo Installing JARVIS PC Controller v2 requirements...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
echo.
echo Done. You can now run start_jarvis.bat
pause
