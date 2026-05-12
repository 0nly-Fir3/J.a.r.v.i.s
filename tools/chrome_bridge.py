
import json
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ChromeAction:
    id: str
    action: str
    payload: Dict[str, Any] = field(default_factory=dict)
    created: float = field(default_factory=time.time)


class ChromeBridge:
    """Local bridge used by the optional Chrome extension.

    The backend cannot directly call Chrome extension APIs. The extension polls
    this bridge for pending actions, runs them in Chrome, then posts results back.
    """

    def __init__(self) -> None:
        self.enabled = True
        self.pending: "queue.Queue[ChromeAction]" = queue.Queue()
        self.results: Dict[str, Dict[str, Any]] = {}
        self.state: Dict[str, Any] = {
            "connected": False,
            "last_seen": 0,
            "last_poll": 0,
            "tabs": [],
            "bookmarks": [],
            "page": {},
            "last_error": "",
        }
        self.lock = threading.RLock()
        Path("data").mkdir(exist_ok=True)
        self.state_file = Path("data/chrome_state.json")

    def status(self) -> Dict[str, Any]:
        with self.lock:
            now = time.time()
            last_seen = float(self.state.get("last_seen", 0) or 0)
            last_poll = float(self.state.get("last_poll", 0) or 0)
            last_any = max(last_seen, last_poll)
            connected = (now - last_any) < 8 if last_any else False
            return {
                "connected": connected,
                "last_seen_seconds_ago": round(now - last_any, 2) if last_any else None,
                "last_state_seconds_ago": round(now - last_seen, 2) if last_seen else None,
                "last_poll_seconds_ago": round(now - last_poll, 2) if last_poll else None,
                "pending_jobs": self.pending.qsize(),
                "tabs": len(self.state.get("tabs", []) or []),
                "bookmarks": len(self.state.get("bookmarks", []) or []),
                "page_title": (self.state.get("page") or {}).get("title", ""),
                "page_url": (self.state.get("page") or {}).get("url", ""),
                "last_error": self.state.get("last_error", ""),
            }

    def heartbeat(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self.lock:
            self.state["connected"] = True
            self.state["last_poll"] = time.time()
            if payload and payload.get("last_error"):
                self.state["last_error"] = str(payload.get("last_error"))[:500]
            return self.status()

    def clear_pending(self) -> int:
        count = 0
        while True:
            try:
                self.pending.get_nowait()
                count += 1
            except queue.Empty:
                break
        return count

    def update_state(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            self.state.update(payload or {})
            self.state["connected"] = True
            self.state["last_seen"] = time.time()
            try:
                self.state_file.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
            except Exception:
                pass
            return self.status()

    def pop_pending(self) -> Optional[Dict[str, Any]]:
        with self.lock:
            self.state["connected"] = True
            self.state["last_poll"] = time.time()
        try:
            action = self.pending.get_nowait()
            while time.time() - action.created > 10:
                try:
                    action = self.pending.get_nowait()
                except queue.Empty:
                    return None
            return {"id": action.id, "action": action.action, "payload": action.payload}
        except queue.Empty:
            return None

    def submit_result(self, action_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            self.results[action_id] = {"result": result, "time": time.time()}
        return {"ok": True}

    def request(self, action: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 4.0) -> Dict[str, Any]:
        # Remove stale jobs so an old command does not block a fresh command.
        now = time.time()
        fresh: List[ChromeAction] = []
        while True:
            try:
                old = self.pending.get_nowait()
                if now - old.created <= 10:
                    fresh.append(old)
            except queue.Empty:
                break
        for old in fresh:
            self.pending.put(old)

        action_id = str(uuid.uuid4())
        self.pending.put(ChromeAction(action_id, action, payload or {}))
        start = time.time()
        while time.time() - start < timeout:
            with self.lock:
                if action_id in self.results:
                    return self.results.pop(action_id).get("result", {})
            time.sleep(0.05)
        return {"ok": False, "error": "Chrome extension did not respond. Reload the patched extension, open a normal website, then try again."}

    def list_tabs_text(self) -> str:
        tabs = self.state.get("tabs", []) or []
        if not tabs:
            return "I do not have Chrome tab data yet. Load the patched JARVIS Chrome extension, open a normal website, then say chrome bridge status."
        lines = []
        for i, tab in enumerate(tabs[:30], start=1):
            active = "*" if tab.get("active") else " "
            lines.append(f"{active} {i}. {tab.get('title','Untitled')} - {tab.get('url','')}")
        return "\n".join(lines)

    def list_bookmarks_text(self, limit: int = 40) -> str:
        bms = self.state.get("bookmarks", []) or []
        if not bms:
            return "I do not have Chrome bookmark data yet. Load the patched JARVIS Chrome extension, or use the file-based bookmark fallback."
        return "\n".join(f"{i}. {b.get('title') or b.get('name') or 'Bookmark'} - {b.get('url','')}" for i, b in enumerate(bms[:limit], start=1))

    def current_page_text(self) -> str:
        page = self.state.get("page", {}) or {}
        text = page.get("selectedText") or page.get("text") or ""
        return text[:20000]

    def page_summary_context(self) -> str:
        page = self.state.get("page", {}) or {}
        elements = (page.get("elements", []) or [])[:80]
        lines = [
            f"Title: {page.get('title','')}",
            f"URL: {page.get('url','')}",
            "Visible elements:",
        ]
        for i, el in enumerate(elements, 1):
            label = el.get("label", "")[:120]
            tag = el.get("tag", "")
            if label:
                lines.append(f"{i}. [{tag}] {label}")
        text = page.get("selectedText") or page.get("text") or ""
        if text:
            lines.append("\nPage text preview:\n" + text[:8000])
        return "\n".join(lines)
