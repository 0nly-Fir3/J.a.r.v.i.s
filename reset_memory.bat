@echo off
cd /d "%~dp0"
del /q data\memory.json 2>nul
del /q data\conversation_history.jsonl 2>nul
echo Memory reset.
pause
