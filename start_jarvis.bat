@echo off
title JARVIS PC Controller v2
cd /d "%~dp0"
echo Starting JARVIS PC Controller v2...
echo Keep this window open while using jarvis_pc_v2.html
echo Local server: http://127.0.0.1:5050
py jarvis_backend.py
pause
