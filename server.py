import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from command_router import CommandRouter
from tools.tts_engine import TTSEngine

load_dotenv()

app = Flask(__name__, static_folder="frontend", static_url_path="")
CORS(app)

router = CommandRouter()
tts = TTSEngine()


@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "provider": "OpenRouter",
        "version": "JARVIS V10 Personal OS",
        "model": os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash"),
        "vision_model": os.getenv("OPENROUTER_VISION_MODEL", os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")),
        "shell_enabled": os.getenv("ENABLE_SHELL", "false").lower() == "true",
        "ocr_status": router.screen.ocr_status(),
    })


@app.route("/commands")
def commands():
    return jsonify({
        "wake": ["hey jarvis", "jarvis"],
        "modes": ["silent mode", "normal mode", "start writing mode", "stop writing mode", "pause writing", "jarvis command close tab"],
        "v10_browser_extension": ["chrome bridge status", "summarize this page", "list chrome tabs", "switch to tab youtube", "click page login", "click first result"],
        "browser": ["close current tab", "reopen closed tab", "new tab", "next tab", "go back", "open the third bookmark", "list bookmarks"],
        "screen": ["what am i looking at", "fix this error", "read screen", "screen targets", "press blue button", "highlight login"],
        "autopilot": ["autopilot research budget controllers and make notes", "research best free AI APIs"],
        "routines": ["create routine called homework mode with open google docs, start writing mode", "start homework mode", "list routines"],
        "custom_commands": ["when I say school site do open bookmark school", "list custom commands"],
        "projects": ["switch to guardian angel project", "save project note ...", "project summary"],
        "files": ["rescan files", "find indexed file homework", "open latest download", "create txt file open it and write ..."],
        "apps": ["open chrome", "close discord", "close file explorer", "switch to spotify", "rescan apps"],
        "memory": ["remember that...", "what do you remember", "forget..."]
    })


@app.route("/chat", methods=["POST"])
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or data.get("text") or "").strip()
    source = data.get("source", "text")
    if not message:
        return jsonify({"reply": "No message received.", "handled": True, "action": "empty"}), 400
    result = router.route(message, source=source)
    return jsonify({
        "reply": result.reply,
        "handled": result.handled,
        "normalized": result.normalized,
        "action": result.action,
        "extra": result.extra or {},
    })


@app.route("/api/memory")
def memory():
    return jsonify({"memory": router.memory.list_memory()})


@app.route("/api/logs")
def logs():
    return jsonify({"logs": router.history.recent(30)})



@app.route("/api/chrome/status")
def chrome_status():
    return jsonify(router.chrome.status())


@app.route("/api/chrome/state", methods=["POST"])
def chrome_state():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(router.chrome.update_state(data))


@app.route("/api/chrome/heartbeat", methods=["GET", "POST"])
def chrome_heartbeat():
    data = request.get_json(force=True, silent=True) if request.method == "POST" else {}
    return jsonify(router.chrome.heartbeat(data or {}))


@app.route("/api/chrome/pending")
def chrome_pending():
    job = router.chrome.pop_pending()
    return jsonify(job or {"ok": True, "idle": True})


@app.route("/api/chrome/clear", methods=["POST"])
def chrome_clear():
    n = router.chrome.clear_pending()
    return jsonify({"ok": True, "cleared": n, "status": router.chrome.status()})


@app.route("/api/chrome/result", methods=["POST"])
def chrome_result():
    data = request.get_json(force=True, silent=True) or {}
    action_id = data.get("id", "")
    result = data.get("result", {})
    return jsonify(router.chrome.submit_result(action_id, result))


@app.route("/api/status")
def full_status():
    return jsonify({
        "health": "ok",
        "chrome": router.chrome.status(),
        "project": router.projects.active(),
        "ocr_status": router.screen.ocr_status(),
        "tts": {"edge_tts_available": tts.available(), "voice": tts.voice},
    })

@app.route("/api/tts/status")
def tts_status():
    return jsonify({
        "ok": True,
        "edge_tts_available": tts.available(),
        "voice": tts.voice,
    })


@app.route("/api/tts", methods=["POST"])
def create_tts():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "No text."}), 400
    path = tts.create_audio(text[:3000])
    if not path:
        return jsonify({"ok": False, "error": "Edge TTS unavailable or failed to create audio."})
    name = Path(path).name
    return jsonify({"ok": True, "url": f"/api/tts/audio/{name}"})


@app.route("/api/tts/audio/<path:name>")
def serve_tts(name: str):
    return send_from_directory(str(Path("data/tts")), name)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
