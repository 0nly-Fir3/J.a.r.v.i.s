JARVIS V10 Chrome Bridge Deadlock Fix

This patch fixes the reason the extension stayed on Checking and CMD showed no /api/chrome lines.

Cause:
The backend ChromeBridge used a normal Lock. heartbeat() and update_state() acquired that lock and then called status(), which tried to acquire the same lock again. This deadlocked the request before Flask could finish it, so Chrome waited forever and the terminal never printed /api/chrome/heartbeat or /api/chrome/state.

Fix:
Changed ChromeBridge to use threading.RLock(), so nested status calls no longer freeze.

Install:
1. Run start.bat.
2. Remove the old JARVIS Chrome extension from chrome://extensions.
3. Load unpacked: chrome_extension folder from this package.
4. Open https://google.com.
5. Click the extension icon. It should connect.
6. In JARVIS type: chrome bridge status, then list chrome tabs.
