
import json
from pathlib import Path
from typing import Dict, List


class ProjectManager:
    def __init__(self) -> None:
        self.path = Path("data/projects.json")
        self.path.parent.mkdir(exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({"active": "general", "projects": {"general": {"notes": [], "files": [], "links": []}}}, indent=2), encoding="utf-8")

    def _load(self) -> Dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"active": "general", "projects": {"general": {"notes": [], "files": [], "links": []}}}

    def _save(self, data: Dict) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def switch(self, name: str) -> str:
        name = name.strip().lower() or "general"
        data = self._load()
        data.setdefault("projects", {}).setdefault(name, {"notes": [], "files": [], "links": []})
        data["active"] = name
        self._save(data)
        return f"Switched to {name} project."

    def active(self) -> str:
        return self._load().get("active", "general")

    def add_note(self, note: str) -> str:
        data = self._load()
        active = data.get("active", "general")
        project = data.setdefault("projects", {}).setdefault(active, {"notes": [], "files": [], "links": []})
        project.setdefault("notes", []).append(note.strip())
        self._save(data)
        return f"Saved note to {active}."

    def summary(self) -> str:
        data = self._load()
        active = data.get("active", "general")
        project = data.get("projects", {}).get(active, {})
        notes = project.get("notes", [])[-10:]
        files = project.get("files", [])[-10:]
        links = project.get("links", [])[-10:]
        lines = [f"Active project: {active}"]
        if notes:
            lines.append("Notes:")
            lines.extend(f"- {n}" for n in notes)
        if files:
            lines.append("Files:")
            lines.extend(f"- {f}" for f in files)
        if links:
            lines.append("Links:")
            lines.extend(f"- {l}" for l in links)
        return "\n".join(lines)
