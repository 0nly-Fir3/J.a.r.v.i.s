import json
import os
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psutil


class AppManager:
    def __init__(self, index_path: str = "data/apps.json", aliases_path: str = "data/site_aliases.json") -> None:
        self.index_path = Path(index_path)
        self.aliases_path = Path(aliases_path)
        self.index_path.parent.mkdir(exist_ok=True)
        if not self.index_path.exists():
            self.scan_apps()

    def scan_apps(self) -> Dict[str, str]:
        apps: Dict[str, str] = {}
        candidates: List[Path] = []
        home = Path.home()
        env_paths = [
            os.getenv("APPDATA", ""),
            os.getenv("PROGRAMDATA", ""),
            str(home / "Desktop"),
            str(home / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs"),
            "C:/ProgramData/Microsoft/Windows/Start Menu/Programs",
        ]
        for raw in env_paths:
            if raw:
                p = Path(raw)
                if p.exists():
                    candidates.append(p)
        for base in candidates:
            if base.name.lower() == "programdata":
                continue
            for ext in ("*.lnk", "*.url", "*.exe"):
                try:
                    for item in base.rglob(ext):
                        name = self._clean_name(item.stem)
                        if name and name not in apps:
                            apps[name] = str(item)
                except Exception:
                    pass
        common_exes = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "cmd": "cmd.exe",
            "command prompt": "cmd.exe",
            "powershell": "powershell.exe",
            "paint": "mspaint.exe",
            "task manager": "taskmgr.exe",
            "settings": "ms-settings:",
            "control panel": "control.exe",
            "file explorer": "explorer.exe",
            "explorer": "explorer.exe",
            "edge": "msedge.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "vs code": "code",
            "visual studio code": "code",
        }
        for app_name, target in common_exes.items():
            apps.setdefault(self._clean_name(app_name), target)
        self.index_path.write_text(json.dumps(apps, indent=2, ensure_ascii=False), encoding="utf-8")
        return apps

    def load(self) -> Dict[str, str]:
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return self.scan_apps()

    def load_aliases(self) -> Dict[str, str]:
        try:
            return json.loads(self.aliases_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def open_app(self, name: str) -> str:
        raw_name = name.strip()
        name = self._clean_name(name)
        if not name:
            return "Tell me which app to open."
        aliases = self.load_aliases()
        if name in aliases:
            return self.open_url(aliases[name], spoken_name=raw_name.title())
        if self._looks_like_url(name):
            return self.open_url(name)
        apps = self.load()
        match, target = self._match(name, apps)
        if not target:
            self.scan_apps()
            apps = self.load()
            match, target = self._match(name, apps)
        if not target:
            return f"I could not find {raw_name}. Try 'rescan apps' or open it once from the Start Menu."
        try:
            if target.startswith("ms-") or target.endswith(":"):
                os.startfile(target)
            elif Path(target).suffix.lower() in [".lnk", ".url", ".exe"] and Path(target).exists():
                os.startfile(target) if hasattr(os, "startfile") else subprocess.Popen([target])
            else:
                subprocess.Popen(target, shell=True)
            return f"Opened {self._pretty_name(match)}."
        except Exception as e:
            try:
                subprocess.Popen(target, shell=True)
                return f"Opened {self._pretty_name(match)}."
            except Exception:
                return f"Could not open {self._pretty_name(match)}."

    def close_app(self, name: str) -> str:
        raw_name = name.strip()
        key = self._clean_name(name)
        if not key:
            return "Tell me which app to close."
        aliases = {
            "chrome": ["chrome"],
            "google chrome": ["chrome"],
            "edge": ["msedge"],
            "file explorer": ["explorer"],
            "explorer": ["explorer"],
            "notepad": ["notepad"],
            "calculator": ["calculator", "calc"],
            "discord": ["discord"],
            "steam": ["steam"],
            "spotify": ["spotify"],
            "roblox studio": ["robloxstudiobeta"],
            "vs code": ["code"],
            "visual studio code": ["code"],
        }
        needles = aliases.get(key, [key.replace(" ", "")])
        killed: List[str] = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                stem = Path(pname).stem.lower()
                if any(n in stem for n in needles):
                    proc.terminate()
                    killed.append(pname)
            except Exception:
                pass
        if not killed:
            return f"I could not find {raw_name} running."
        return f"Closed {self._pretty_name(key)}."

    def open_url(self, url: str, spoken_name: Optional[str] = None) -> str:
        url = url.strip()
        if not re.match(r"^https?://", url):
            url = "https://" + url
        webbrowser.open(url)
        if spoken_name:
            return f"Opened {spoken_name}."
        clean = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
        return f"Opened {clean}."

    def google(self, query: str) -> str:
        query = query.strip()
        webbrowser.open("https://www.google.com/search?q=" + query.replace(" ", "+"))
        return f"Searching Google for {query}."

    def youtube(self, query: str) -> str:
        query = query.strip()
        webbrowser.open("https://www.youtube.com/results?search_query=" + query.replace(" ", "+"))
        return f"Searching YouTube for {query}."

    def list_apps(self, limit: int = 80) -> str:
        apps = sorted(self.load().keys())[:limit]
        return "\n".join(apps) if apps else "No apps indexed yet."

    def _clean_name(self, name: str) -> str:
        name = (name or "").lower().strip()
        name = re.sub(r"\b(app|application|program)\b", "", name)
        name = re.sub(r"[^a-z0-9åäö \-_\.]+", "", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name

    def _pretty_name(self, name: str) -> str:
        special = {
            "chrome": "Chrome",
            "google chrome": "Chrome",
            "file explorer": "File Explorer",
            "explorer": "File Explorer",
            "vs code": "VS Code",
            "visual studio code": "VS Code",
            "cmd": "Command Prompt",
        }
        return special.get(name.lower(), name.title())

    def _match(self, name: str, apps: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
        if name in apps:
            return name, apps[name]
        for app, target in apps.items():
            if name in app or app in name:
                return app, target
        import difflib
        m = difflib.get_close_matches(name, list(apps.keys()), n=1, cutoff=0.62)
        if m:
            return m[0], apps[m[0]]
        return None, None

    def _looks_like_url(self, text: str) -> bool:
        return "." in text and " " not in text and not text.endswith(".exe")
