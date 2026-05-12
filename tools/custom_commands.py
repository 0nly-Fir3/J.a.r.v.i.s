
import json
import re
from pathlib import Path
from typing import Dict, Optional


class CustomCommandManager:
    def __init__(self) -> None:
        self.path = Path("data/custom_commands.json")
        self.path.parent.mkdir(exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def _load(self) -> Dict[str, str]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data: Dict[str, str]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def teach_from_text(self, text: str) -> Optional[str]:
        # when I say X, do Y
        m = re.search(r"when i say ['\"]?(.+?)['\"]?,?\s+(?:do|run|execute|say)\s+(.+)$", text, flags=re.I)
        if not m:
            return None
        trigger = m.group(1).strip().lower()
        action = m.group(2).strip()
        data = self._load()
        data[trigger] = action
        self._save(data)
        return f"Learned custom command: {trigger}."

    def resolve(self, text: str) -> Optional[str]:
        data = self._load()
        low = text.lower().strip()
        return data.get(low)

    def list(self) -> str:
        data = self._load()
        if not data:
            return "No custom commands saved yet."
        return "\n".join(f"{k} -> {v}" for k, v in data.items())
