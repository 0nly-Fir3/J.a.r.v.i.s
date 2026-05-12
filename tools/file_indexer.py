
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional


class FileIndexer:
    def __init__(self) -> None:
        self.path = Path("data/file_index.json")
        self.path.parent.mkdir(exist_ok=True)
        self.roots = [Path.home()/"Desktop", Path.home()/"Downloads", Path.home()/"Documents"]

    def index(self, max_files: int = 5000) -> str:
        rows: List[Dict] = []
        for root in self.roots:
            if not root.exists():
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not d.startswith(".") and d.lower() not in {"node_modules", ".git", "appdata"}]
                for name in filenames:
                    p = Path(dirpath) / name
                    try:
                        st = p.stat()
                        rows.append({"name": name, "path": str(p), "mtime": st.st_mtime, "size": st.st_size, "ext": p.suffix.lower()})
                        if len(rows) >= max_files:
                            raise StopIteration
                    except StopIteration:
                        break
                    except Exception:
                        pass
                if len(rows) >= max_files:
                    break
        rows.sort(key=lambda x: x.get("mtime", 0), reverse=True)
        self.path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        return f"Indexed {len(rows)} files."

    def _load(self) -> List[Dict]:
        if not self.path.exists():
            self.index()
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def find(self, query: str, limit: int = 10) -> str:
        q = query.lower().strip()
        rows = [r for r in self._load() if q in r.get("name", "").lower() or q in r.get("path", "").lower()]
        if not rows:
            return "No indexed files matched. Say rescan files and try again."
        return "\n".join(f"{i+1}. {Path(r['path']).name} - {r['path']}" for i, r in enumerate(rows[:limit]))

    def latest(self, ext: Optional[str] = None) -> Optional[str]:
        rows = self._load()
        if ext:
            ext = ext.lower() if ext.startswith(".") else "." + ext.lower()
            rows = [r for r in rows if r.get("ext") == ext]
        return rows[0]["path"] if rows else None
