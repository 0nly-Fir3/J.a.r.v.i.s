J.A.R.V.I.S Full PC Control - Google AI Studio Version
======================================================

This is the Groq/Grok-style operational local assistant, but converted to Google AI Studio / Gemini.

HOW TO RUN
----------
1. Extract the folder.
2. Double-click start.bat.
3. If .env opens, paste your key:

   GEMINI_API_KEY=your_google_ai_studio_key_here

4. Save .env.
5. Open:

   http://127.0.0.1:5050

IMPORTANT
---------
Do not open frontend/index.html directly. Use http://127.0.0.1:5050.

COMMANDS
--------
take screenshot
screenshot and analyze it
open notepad
open calculator
open chrome
open downloads
open desktop
open C:\Users\YourName\Downloads
go to youtube.com
google best RTX 3080 driver
youtube packdraw highlights
press ctrl + l
press alt + tab
press win + r
type hello world
paste hello world
copy hello world
read clipboard
click
right click
double click
move mouse to 500 300
scroll up
scroll down
scroll -5
system info
list files in downloads
list files in desktop
find file homework

SHELL COMMANDS
--------------
Shell commands are disabled by default for safety.
To enable them, edit .env:

ENABLE_SHELL=true

Then you can say:
run command ipconfig
cmd dir
terminal whoami

Dangerous commands are blocked.

SAFETY
------
PyAutoGUI has a failsafe. Move your mouse to the top-left corner of the screen to stop runaway mouse actions.

TROUBLESHOOTING
---------------
If 127.0.0.1:5050 refuses connection:
- The server is not running.
- Run start.bat again.

If voice says no-speech:
- The browser did not hear audio.
- Use Chrome/Edge.
- Make sure microphone permission is allowed for http://127.0.0.1:5050.

If screenshot does not work:
- Run start.bat again so pyautogui and pillow install correctly.

If Gemini does not answer:
- Check .env has GEMINI_API_KEY.
- Restart start.bat after editing .env.
