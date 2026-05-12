JARVIS V10 Chrome Bridge Silent Fix

This patch fixes the case where JARVIS thinks for a few seconds and then says/does nothing when using Chrome bridge commands.

Fixes included:
- Server-side wake-word stripping: typed commands like "hey jarvis list chrome tabs" now work.
- Chrome commands bypass the AI planner so they return immediately.
- Extension heartbeat endpoint added.
- Pending bridge jobs are cleared when stale.
- Extension posts heartbeat even when the active tab is restricted.
- Popup now shows Connected / tabs / bookmarks / last error instead of staying on Checking.

Install:
1. Extract this ZIP.
2. Copy your old .env into this folder.
3. Run start.bat.
4. Remove the old Chrome extension from chrome://extensions.
5. Load unpacked -> select this package chrome_extension folder.
6. Open https://google.com in Chrome.
7. In JARVIS type: chrome bridge status
8. Then type: list chrome tabs

If it still fails, open CMD and check for:
POST /api/chrome/heartbeat 200
POST /api/chrome/state 200
GET /api/chrome/pending 200
