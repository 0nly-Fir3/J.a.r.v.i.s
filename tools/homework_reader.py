import os
from pathlib import Path
from typing import Optional, Tuple

from docx import Document
from pypdf import PdfReader

from .screen_reader import ScreenReader


class HomeworkReader:
    def __init__(self, screen_reader: ScreenReader) -> None:
        self.screen_reader = screen_reader

    def read_file(self, path: str) -> Tuple[str, str]:
        p = Path(path.strip().strip('"'))
        if not p.exists():
            found = self.find_latest_homework(path)
            if found:
                p = found
            else:
                return "", f"File not found: {path}"
        ext = p.suffix.lower()
        try:
            if ext in [".txt", ".md", ".csv", ".log"]:
                return p.read_text(encoding="utf-8", errors="ignore"), str(p)
            if ext == ".docx":
                doc = Document(str(p))
                return "\n".join(par.text for par in doc.paragraphs), str(p)
            if ext == ".pdf":
                reader = PdfReader(str(p))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                return text, str(p)
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
                boxes = self.screen_reader.ocr(str(p))
                return self.screen_reader.boxes_to_text(boxes), str(p)
            return "", f"Unsupported file type: {ext}"
        except Exception as e:
            return "", f"Could not read file: {e}"

    def find_latest_homework(self, query: str = "") -> Optional[Path]:
        bases = [Path.home() / "Downloads", Path.home() / "Desktop", Path.home() / "Documents"]
        exts = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}
        files = []
        q = query.lower().strip()
        for base in bases:
            if not base.exists():
                continue
            for root, dirs, names in os.walk(base):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for name in names:
                    p = Path(root) / name
                    if p.suffix.lower() not in exts:
                        continue
                    if q and q not in name.lower() and "homework" not in name.lower() and "uppgift" not in name.lower():
                        continue
                    try:
                        files.append((p.stat().st_mtime, p))
                    except Exception:
                        pass
        if not files:
            return None
        return sorted(files, reverse=True)[0][1]
