import json
import os
import time
from typing import Any, Dict, List


class MemoryManager:
    def __init__(self, path: str = "data/memory.json", history_path: str = "data/conversation_history.jsonl") -> None:
        self.path = path
        self.history_path = history_path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write({"facts": [], "projects": {}, "preferences": {}, "recent_commands": []})

    def _read(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"facts": [], "projects": {}, "preferences": {}, "recent_commands": []}

    def _write(self, data: Dict[str, Any]) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def remember(self, text: str, category: str = "facts") -> str:
        text = text.strip()
        if not text:
            return "Tell me what to remember."
        data = self._read()
        item = {"text": text, "category": category, "time": int(time.time())}
        facts: List[Dict[str, Any]] = data.setdefault("facts", [])
        if not any(f.get("text", "").lower() == text.lower() for f in facts):
            facts.append(item)
        self._write(data)
        return f"Remembered: {text}"

    def forget(self, query: str) -> str:
        query = query.strip().lower()
        data = self._read()
        facts = data.get("facts", [])
        before = len(facts)
        if not query or query in ["everything", "all"]:
            data["facts"] = []
            self._write(data)
            return "I cleared all saved facts."
        data["facts"] = [f for f in facts if query not in f.get("text", "").lower()]
        removed = before - len(data["facts"])
        self._write(data)
        return f"Removed {removed} matching memory item." if removed else "I could not find that in memory."

    def list_memory(self) -> str:
        data = self._read()
        facts = data.get("facts", [])
        if not facts:
            return "I do not have any saved memories yet."
        lines = [f"{i + 1}. {f.get('text', '')}" for i, f in enumerate(facts[-30:])]
        return "Here is what I remember:\n" + "\n".join(lines)

    def context(self) -> str:
        data = self._read()
        facts = data.get("facts", [])[-20:]
        if not facts:
            return ""
        return "Saved user memory:\n" + "\n".join(f"- {f.get('text', '')}" for f in facts)

    def log_command(self, command: str, normalized: str, result: str) -> None:
        data = self._read()
        recent = data.setdefault("recent_commands", [])
        recent.append({"time": int(time.time()), "command": command, "normalized": normalized, "result": result[:400]})
        data["recent_commands"] = recent[-80:]
        self._write(data)

    def add_history(self, role: str, content: str) -> None:
        os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": int(time.time()), "role": role, "content": content}, ensure_ascii=False) + "\n")

    def recent_history(self, limit: int = 12) -> List[Dict[str, str]]:
        if not os.path.exists(self.history_path):
            return []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                rows = [json.loads(line) for line in f if line.strip()]
            return [{"role": r.get("role", "user"), "content": r.get("content", "")} for r in rows[-limit:]]
        except Exception:
            return []
