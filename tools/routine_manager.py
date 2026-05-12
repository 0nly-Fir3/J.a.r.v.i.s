
import json
import re
from pathlib import Path
from typing import Dict, List, Optional


class RoutineManager:
    def __init__(self) -> None:
        self.path = Path("data/routines.json")
        self.path.parent.mkdir(exist_ok=True)
        if not self.path.exists():
            defaults = {
                "homework mode": ["open google docs", "open folder documents", "start writing mode"],
                "coding mode": ["open chrome", "open folder documents"],
                "research mode": ["open chrome", "new tab"],
            }
            self.path.write_text(json.dumps(defaults, indent=2), encoding="utf-8")

    def _load(self) -> Dict[str, List[str]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data: Dict[str, List[str]]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def list(self) -> str:
        data = self._load()
        if not data:
            return "No routines saved yet."
        return "\n".join(f"{name}: " + " | ".join(steps) for name, steps in data.items())

    def save(self, name: str, steps_text: str) -> str:
        name = name.strip().lower()
        steps = [s.strip() for s in re.split(r"\s*(?:,|;| then | and then )\s*", steps_text, flags=re.I) if s.strip()]
        if not name or not steps:
            return "Say it like: create routine called homework mode with open Google Docs, open documents folder."
        data = self._load()
        data[name] = steps
        self._save(data)
        return f"Saved routine {name} with {len(steps)} step(s)."

    def match(self, text: str) -> Optional[List[str]]:
        low = text.lower().strip()
        data = self._load()
        for name, steps in data.items():
            if low in [name, f"start {name}", f"run {name}", f"activate {name}"]:
                return steps
        return None
