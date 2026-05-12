import json
import os
import re
import time
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pyautogui


class BrowserController:
    def __init__(self, browser: str = "chrome") -> None:
        self.browser = browser.lower().strip() or "chrome"

    def _hotkey(self, *keys: str) -> str:
        pyautogui.hotkey(*keys)
        return "Done."

    def new_tab(self) -> str:
        return self._hotkey("ctrl", "t")

    def close_tab(self) -> str:
        return self._hotkey("ctrl", "w")

    def reopen_closed_tab(self) -> str:
        return self._hotkey("ctrl", "shift", "t")

    def next_tab(self) -> str:
        return self._hotkey("ctrl", "tab")

    def previous_tab(self) -> str:
        return self._hotkey("ctrl", "shift", "tab")

    def refresh(self) -> str:
        return self._hotkey("ctrl", "r")

    def go_back(self) -> str:
        return self._hotkey("alt", "left")

    def go_forward(self) -> str:
        return self._hotkey("alt", "right")

    def address_bar(self) -> str:
        return self._hotkey("ctrl", "l")

    def open_url(self, url: str, spoken_name: Optional[str] = None) -> str:
        url = url.strip()
        if not re.match(r"^https?://", url, flags=re.I):
            url = "https://" + url
        webbrowser.open(url)
        return f"Opened {spoken_name or url}."

    def search_google(self, query: str) -> str:
        query = query.strip()
        if not query:
            return "Tell me what to search for."
        webbrowser.open("https://www.google.com/search?q=" + query.replace(" ", "+"))
        return f"Searching Google for {query}."

    def search_youtube(self, query: str) -> str:
        query = query.strip()
        if not query:
            return "Tell me what to search for."
        webbrowser.open("https://www.youtube.com/results?search_query=" + query.replace(" ", "+"))
        return f"Searching YouTube for {query}."

    def open_google_docs(self) -> str:
        return self.open_url("https://docs.new", "Google Docs")

    def open_google_sheets(self) -> str:
        return self.open_url("https://sheets.new", "Google Sheets")

    def open_google_slides(self) -> str:
        return self.open_url("https://slides.new", "Google Slides")

    def list_bookmarks(self, limit: int = 30) -> str:
        bookmarks = self._chrome_bookmarks()
        if not bookmarks:
            return "I could not find Chrome bookmarks on this Windows profile."
        lines = [f"{i + 1}. {b['name']} - {b['url']}" for i, b in enumerate(bookmarks[:limit])]
        return "\n".join(lines)

    def open_bookmark(self, query: str) -> str:
        bookmarks = self._chrome_bookmarks()
        if not bookmarks:
            return "I could not find Chrome bookmarks."
        q = query.lower().strip()
        n = self._ordinal_to_number(q)
        if n and 1 <= n <= len(bookmarks):
            b = bookmarks[n - 1]
            webbrowser.open(b["url"])
            return f"Opened bookmark {n}: {b['name']}."
        import difflib
        names = [b["name"].lower() for b in bookmarks]
        match_idx = None
        for i, b in enumerate(bookmarks):
            if q and (q in b["name"].lower() or q in b["url"].lower()):
                match_idx = i
                break
        if match_idx is None:
            m = difflib.get_close_matches(q, names, n=1, cutoff=0.45)
            if m:
                match_idx = names.index(m[0])
        if match_idx is None:
            return f"I could not find a bookmark matching {query}. Say 'list bookmarks' to see them."
        b = bookmarks[match_idx]
        webbrowser.open(b["url"])
        return f"Opened bookmark: {b['name']}."

    def _chrome_bookmarks(self) -> List[Dict[str, str]]:
        local = os.getenv("LOCALAPPDATA", "")
        candidates = []
        if local:
            base = Path(local) / "Google" / "Chrome" / "User Data"
            candidates.extend([
                base / "Default" / "Bookmarks",
                base / "Profile 1" / "Bookmarks",
                base / "Profile 2" / "Bookmarks",
                base / "Profile 3" / "Bookmarks",
            ])
        bookmarks: List[Dict[str, str]] = []
        for path in candidates:
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    roots = data.get("roots", {})
                    for root in roots.values():
                        self._collect_bookmarks(root, bookmarks)
                except Exception:
                    pass
        seen = set()
        unique: List[Dict[str, str]] = []
        for b in bookmarks:
            key = b["url"]
            if key not in seen:
                seen.add(key)
                unique.append(b)
        return unique

    def _collect_bookmarks(self, node: Dict, out: List[Dict[str, str]]) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "url" and node.get("url"):
            out.append({"name": node.get("name", "Bookmark"), "url": node["url"]})
        for child in node.get("children", []) or []:
            self._collect_bookmarks(child, out)

    def _ordinal_to_number(self, text: str) -> Optional[int]:
        text = text.lower().strip()
        words = {
            "first": 1,
            "second": 2,
            "third": 3,
            "fourth": 4,
            "fifth": 5,
            "sixth": 6,
            "seventh": 7,
            "eighth": 8,
            "ninth": 9,
            "tenth": 10,
        }
        for word, value in words.items():
            if word in text:
                return value
        m = re.search(r"\b(\d+)(st|nd|rd|th)?\b", text)
        if m:
            return int(m.group(1))
        return None
