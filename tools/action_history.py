import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class ActionHistory:
    def __init__(self, path: str = "data/command_log.jsonl", undo_path: str = "data/undo_stack.json") -> None:
        self.path = Path(path)
        self.undo_path = Path(undo_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.undo_path.exists():
            self._write_undo([])

    def log(self, raw: str, normalized: str, action: str, reply: str, extra: Optional[Dict[str, Any]] = None) -> None:
        row = {
            "time": int(time.time()),
            "raw": raw,
            "normalized": normalized,
            "action": action,
            "reply": (reply or "")[:800],
            "extra": extra or {},
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
            return [json.loads(line) for line in lines if line.strip()]
        except Exception:
            return []

    def format_recent(self, limit: int = 10) -> str:
        rows = self.recent(limit)
        if not rows:
            return "No command log yet."
        out = []
        for i, row in enumerate(rows, 1):
            out.append(f"{i}. heard='{row.get('raw','')}' | normalized='{row.get('normalized','')}' | action={row.get('action','')} | reply={row.get('reply','')[:120]}")
        return "Recent command log:\n" + "\n".join(out)

    def clear(self) -> str:
        try:
            if self.path.exists():
                self.path.unlink()
            self._write_undo([])
            return "Command log cleared."
        except Exception as e:
            return f"Could not clear command log: {e}"

    def push_undo(self, kind: str, label: str, payload: Optional[Dict[str, Any]] = None) -> None:
        stack = self._read_undo()
        stack.append({"time": int(time.time()), "kind": kind, "label": label, "payload": payload or {}})
        self._write_undo(stack[-25:])

    def pop_undo(self) -> Optional[Dict[str, Any]]:
        stack = self._read_undo()
        if not stack:
            return None
        item = stack.pop()
        self._write_undo(stack)
        return item

    def peek_undo(self) -> Optional[Dict[str, Any]]:
        stack = self._read_undo()
        return stack[-1] if stack else None

    def _read_undo(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.undo_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write_undo(self, stack: List[Dict[str, Any]]) -> None:
        self.undo_path.parent.mkdir(parents=True, exist_ok=True)
        self.undo_path.write_text(json.dumps(stack, indent=2, ensure_ascii=False), encoding="utf-8")
