import os
import re
import sys
import json
import time
import glob
import shutil
import socket
import platform
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

try:
    import pyautogui
except Exception:
    pyautogui = None

try:
    import pyperclip
except Exception:
    pyperclip = None

try:
    import psutil
except Exception:
    psutil = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
SCREENSHOT_DIR = BASE_DIR / "screenshots"
LOG_DIR = BASE_DIR / "logs"
SCREENSHOT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app)

if pyautogui:
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
ENABLE_SHELL = os.getenv("ENABLE_SHELL", "false").lower() == "true"
client = genai.Client(api_key=API_KEY) if genai and API_KEY else None

APP_ALIASES = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "control panel": "control.exe",
    "settings": "ms-settings:",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "discord": "discord.exe",
    "spotify": "spotify.exe",
    "steam": "steam.exe",
    "vscode": "code.exe",
    "visual studio code": "code.exe",
}

SAFE_URL_RE = re.compile(r"^(https?://|www\.)", re.I)

SYSTEM_PROMPT = """
You are J.A.R.V.I.S, Mustafa's local Windows PC assistant.
You can answer questions, but local computer control is handled by Python tools.
Be direct, short, and useful. If the user asks to control the computer, explain the action result.
Never claim you took an action unless the tool result says it happened.
""".strip()


def log_event(event):
    try:
        with open(LOG_DIR / "jarvis.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": datetime.now().isoformat(), **event}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def ok(reply, data=None):
    payload = {"reply": reply, "ok": True}
    if data is not None:
        payload["data"] = data
    log_event({"ok": True, "reply": reply, "data": data})
    return jsonify(payload)


def fail(reply, code=400, data=None):
    payload = {"reply": reply, "ok": False}
    if data is not None:
        payload["data"] = data
    log_event({"ok": False, "reply": reply, "data": data})
    return jsonify(payload), code


def clean_text(s):
    return (s or "").strip()


def desktop_path():
    return Path.home() / "Desktop"


def downloads_path():
    return Path.home() / "Downloads"


def documents_path():
    return Path.home() / "Documents"


def take_screenshot(analyze=False, prompt="Describe what is visible on this Windows screenshot."):
    if not pyautogui:
        return False, "pyautogui is not installed. Run start.bat again.", None
    filename = f"screenshot_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png"
    path = SCREENSHOT_DIR / filename
    img = pyautogui.screenshot()
    img.save(path)

    if analyze and client and types:
        try:
            data = path.read_bytes()
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=data, mime_type="image/png")
                ]
            )
            text = response.text or "Screenshot saved, but Gemini returned no description."
            return True, f"Screenshot saved: {path}\n\n{text}", {"path": str(path), "analysis": text}
        except Exception as e:
            return True, f"Screenshot saved: {path}\nGemini image analysis failed: {e}", {"path": str(path)}
    return True, f"Screenshot saved: {path}", {"path": str(path)}


def open_app(name):
    target = APP_ALIASES.get(name.lower().strip(), name.strip())
    try:
        if target.startswith("ms-settings:"):
            os.startfile(target)
        elif target.lower().endswith(".exe") or "\\" in target or "/" in target:
            subprocess.Popen(target, shell=True)
        else:
            subprocess.Popen(target, shell=True)
        return True, f"Opened {name}.", {"target": target}
    except Exception as e:
        return False, f"Could not open {name}: {e}", None


def open_path(path_text):
    raw = path_text.strip().strip('"')
    aliases = {
        "desktop": desktop_path(),
        "downloads": downloads_path(),
        "documents": documents_path(),
        "document": documents_path(),
        "home": Path.home(),
    }
    p = aliases.get(raw.lower(), Path(raw).expanduser())
    try:
        if not p.exists():
            return False, f"Path does not exist: {p}", None
        os.startfile(str(p))
        return True, f"Opened: {p}", {"path": str(p)}
    except Exception as e:
        return False, f"Could not open path: {e}", None


def open_website(text):
    import webbrowser
    url = text.strip()
    if not url:
        return False, "No website given.", None
    if not SAFE_URL_RE.match(url):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return True, f"Opened website: {url}", {"url": url}
    except Exception as e:
        return False, f"Could not open website: {e}", None


def google_search(query):
    import webbrowser
    q = query.strip()
    if not q:
        return False, "No search query given.", None
    url = "https://www.google.com/search?q=" + subprocess.list2cmdline([q]).replace(" ", "+").replace('"', "")
    webbrowser.open(url)
    return True, f"Searching Google for: {q}", {"query": q, "url": url}


def youtube_search(query):
    import webbrowser
    q = query.strip()
    if not q:
        return False, "No YouTube search query given.", None
    url = "https://www.youtube.com/results?search_query=" + subprocess.list2cmdline([q]).replace(" ", "+").replace('"', "")
    webbrowser.open(url)
    return True, f"Searching YouTube for: {q}", {"query": q, "url": url}


def press_keys(keys):
    if not pyautogui:
        return False, "pyautogui is not installed.", None
    parts = [k.strip().lower() for k in re.split(r"\s*\+\s*|\s*,\s*", keys) if k.strip()]
    mapping = {"windows": "win", "control": "ctrl", "escape": "esc", "return": "enter", "delete": "del"}
    parts = [mapping.get(k, k) for k in parts]
    if not parts:
        return False, "No keys given.", None
    try:
        pyautogui.hotkey(*parts)
        return True, f"Pressed: {' + '.join(parts)}", {"keys": parts}
    except Exception as e:
        return False, f"Could not press keys: {e}", None


def type_text(text):
    if not pyautogui:
        return False, "pyautogui is not installed.", None
    try:
        pyautogui.write(text, interval=0.01)
        return True, "Typed the text.", {"text": text}
    except Exception:
        if pyperclip:
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            return True, "Typed/pasted the text.", {"text": text}
        return False, "Typing failed. Try installing pyperclip or use paste text command.", None


def paste_text(text):
    if not pyperclip or not pyautogui:
        return False, "pyperclip and pyautogui are required.", None
    try:
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        return True, "Pasted the text.", {"text": text}
    except Exception as e:
        return False, f"Could not paste text: {e}", None


def clipboard_get():
    if not pyperclip:
        return False, "pyperclip is not installed.", None
    try:
        text = pyperclip.paste()
        return True, f"Clipboard: {text[:1500]}", {"clipboard": text}
    except Exception as e:
        return False, f"Could not read clipboard: {e}", None


def clipboard_set(text):
    if not pyperclip:
        return False, "pyperclip is not installed.", None
    try:
        pyperclip.copy(text)
        return True, "Copied to clipboard.", {"text": text}
    except Exception as e:
        return False, f"Could not copy to clipboard: {e}", None


def mouse_action(cmd):
    if not pyautogui:
        return False, "pyautogui is not installed.", None
    c = cmd.lower().strip()
    try:
        if "double" in c:
            pyautogui.doubleClick()
            return True, "Double-clicked.", None
        if "right" in c:
            pyautogui.rightClick()
            return True, "Right-clicked.", None
        if "click" in c:
            pyautogui.click()
            return True, "Clicked.", None
        m = re.search(r"move(?: mouse)?(?: to)?\s+(-?\d+)\s*,?\s+(-?\d+)", c)
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            pyautogui.moveTo(x, y, duration=0.15)
            return True, f"Moved mouse to {x}, {y}.", {"x": x, "y": y}
        m = re.search(r"scroll\s+(-?\d+)", c)
        if m:
            amount = int(m.group(1))
            pyautogui.scroll(amount)
            return True, f"Scrolled {amount}.", {"amount": amount}
        if "scroll up" in c:
            pyautogui.scroll(5)
            return True, "Scrolled up.", None
        if "scroll down" in c:
            pyautogui.scroll(-5)
            return True, "Scrolled down.", None
        return False, "Mouse command not understood.", None
    except Exception as e:
        return False, f"Mouse command failed: {e}", None


def get_system_info():
    info = {
        "computer": socket.gethostname(),
        "user": os.getenv("USERNAME") or os.getenv("USER"),
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "cwd": str(BASE_DIR),
    }
    if psutil:
        try:
            info.update({
                "cpu_percent": psutil.cpu_percent(interval=0.3),
                "ram_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage(str(Path.home())).percent,
                "battery": None,
            })
            bat = psutil.sensors_battery()
            if bat:
                info["battery"] = {"percent": bat.percent, "plugged": bat.power_plugged}
        except Exception:
            pass
    reply = "System info:\n" + "\n".join(f"- {k}: {v}" for k, v in info.items())
    return True, reply, info


def list_files(location="downloads", limit=20):
    p = {"downloads": downloads_path(), "desktop": desktop_path(), "documents": documents_path()}.get(location.lower(), Path(location).expanduser())
    if not p.exists():
        return False, f"Location does not exist: {p}", None
    items = sorted(p.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]
    lines = [f"- {i.name}{'/' if i.is_dir() else ''}" for i in items]
    return True, f"Latest files in {p}:\n" + "\n".join(lines), {"path": str(p), "items": [i.name for i in items]}


def find_files(query, location=None, limit=30):
    root = Path(location).expanduser() if location else Path.home()
    if not root.exists():
        return False, f"Search location does not exist: {root}", None
    q = query.lower().strip()
    results = []
    try:
        for path in root.rglob("*"):
            if len(results) >= limit:
                break
            if q in path.name.lower():
                results.append(str(path))
    except Exception as e:
        if not results:
            return False, f"File search failed: {e}", None
    if not results:
        return True, f"No files found for: {query}", {"results": []}
    return True, "Found files:\n" + "\n".join(f"- {r}" for r in results), {"results": results}


def run_shell(command):
    if not ENABLE_SHELL:
        return False, "Shell command execution is disabled. Set ENABLE_SHELL=true in .env to enable it.", None
    dangerous = ["format ", "del /s", "rm -rf", "shutdown", "cipher /w", "diskpart", "bcdedit", "reg delete"]
    low = command.lower()
    if any(d in low for d in dangerous):
        return False, "Blocked a dangerous command.", None
    try:
        completed = subprocess.run(command, shell=True, text=True, capture_output=True, timeout=20, cwd=str(Path.home()))
        out = (completed.stdout or "") + (completed.stderr or "")
        if len(out) > 3000:
            out = out[:3000] + "\n...output cut..."
        return True, f"Command finished with code {completed.returncode}:\n{out}", {"returncode": completed.returncode, "output": out}
    except Exception as e:
        return False, f"Command failed: {e}", None


def route_tool(message):
    msg = clean_text(message)
    low = msg.lower()

    if any(x in low for x in ["take screenshot", "screenshot", "screen shot", "capture screen"]):
        analyze = any(x in low for x in ["analyze", "read", "what is on", "what's on", "describe", "look at"])
        return take_screenshot(analyze=analyze, prompt=msg)

    m = re.search(r"^(open|launch|start)\s+(.+)$", low)
    if m:
        target_original = msg[m.start(2):].strip()
        if SAFE_URL_RE.match(target_original) or ".com" in target_original or ".se" in target_original or ".net" in target_original or ".org" in target_original:
            return open_website(target_original)
        if target_original.lower() in ["desktop", "downloads", "documents", "home"] or ":\\" in target_original or target_original.startswith("~"):
            return open_path(target_original)
        return open_app(target_original)

    m = re.search(r"^(go to|open website|website)\s+(.+)$", low)
    if m:
        target_original = msg[m.start(2):].strip()
        return open_website(target_original)

    m = re.search(r"^(search google for|google|search for)\s+(.+)$", low)
    if m:
        query = msg[m.start(2):].strip()
        return google_search(query)

    m = re.search(r"^(search youtube for|youtube)\s+(.+)$", low)
    if m:
        query = msg[m.start(2):].strip()
        return youtube_search(query)

    m = re.search(r"^(press|hotkey)\s+(.+)$", low)
    if m:
        keys = msg[m.start(2):].strip()
        return press_keys(keys)

    m = re.search(r"^(type|write)\s+(.+)$", msg, flags=re.I | re.S)
    if m:
        return type_text(m.group(2).strip())

    m = re.search(r"^(paste)\s+(.+)$", msg, flags=re.I | re.S)
    if m:
        return paste_text(m.group(2).strip())

    m = re.search(r"^(copy|copy to clipboard)\s+(.+)$", msg, flags=re.I | re.S)
    if m:
        return clipboard_set(m.group(2).strip())

    if low in ["read clipboard", "what is in clipboard", "clipboard"]:
        return clipboard_get()

    if any(low.startswith(x) for x in ["click", "right click", "double click", "move mouse", "scroll", "scroll up", "scroll down"]):
        return mouse_action(msg)

    if low in ["system info", "pc info", "computer info", "status", "pc status"] or "system information" in low:
        return get_system_info()

    m = re.search(r"^(list files|show files)(?: in)?\s*(downloads|desktop|documents)?", low)
    if m:
        return list_files(m.group(2) or "downloads")

    m = re.search(r"^(find file|search file|find files|search files)\s+(.+)$", low)
    if m:
        query = msg[m.start(2):].strip()
        return find_files(query)

    m = re.search(r"^(run command|cmd|terminal)\s+(.+)$", msg, flags=re.I | re.S)
    if m:
        return run_shell(m.group(2).strip())

    return None


def ask_gemini(message):
    if not client:
        return "Google AI Studio is not configured. Add GEMINI_API_KEY to .env and restart."
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=f"{SYSTEM_PROMPT}\n\nUser: {message}\nJ.A.R.V.I.S:"
        )
        return response.text or "I could not generate a response."
    except Exception as e:
        return f"Gemini API error: {e}"


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "provider": "Google AI Studio / Gemini",
        "model": MODEL_NAME,
        "api_key_loaded": bool(API_KEY),
        "tools": {
            "pyautogui": bool(pyautogui),
            "pyperclip": bool(pyperclip),
            "psutil": bool(psutil),
            "shell_enabled": ENABLE_SHELL,
        }
    })


@app.route("/commands")
def commands():
    return jsonify({
        "commands": [
            "take screenshot",
            "screenshot and analyze it",
            "open notepad / open calculator / open chrome",
            "open downloads / open desktop / open C:\\path\\folder",
            "open youtube.com / go to google.com",
            "google RTX 3080 drivers / youtube packdraw highlights",
            "press ctrl + l / press alt + tab / press win + r",
            "type hello world",
            "paste hello world",
            "copy this text",
            "read clipboard",
            "click / right click / double click",
            "move mouse to 500 300",
            "scroll up / scroll down / scroll -5",
            "system info / pc status",
            "list files in downloads / list files in desktop",
            "find file homework",
            "run command ipconfig  (requires ENABLE_SHELL=true in .env)",
        ]
    })


@app.route("/chat", methods=["POST"])
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    message = clean_text(data.get("message") or data.get("text") or "")
    if not message:
        return fail("No message provided.", 400)

    tool_result = route_tool(message)
    if tool_result is not None:
        success, reply, extra = tool_result
        return ok(reply, extra) if success else fail(reply, 400, extra)

    reply = ask_gemini(message)
    return ok(reply)


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5050"))
    app.run(host=host, port=port, debug=True)
