@echo off
setlocal
cd /d "%~dp0"
echo This will remove the old virtual environment and reinstall packages.
echo Your .env API key, memory, screenshots, and generated files will not be deleted.
pause
if exist ".venv" (
  rmdir /s /q ".venv"
)
call "start.bat"
