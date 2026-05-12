import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pyautogui


@dataclass
class TaskResult:
    handled: bool
    reply: str
    action: str = "task"
    extra: Optional[Dict[str, Any]] = None


class TaskPlanner:
    def __init__(self, ai, pc, apps, browser, files, windows) -> None:
        self.ai = ai
        self.pc = pc
        self.apps = apps
        self.browser = browser
        self.files = files
        self.windows = windows
        self.last_generated_text = ""
        self.last_created_file = ""

    def plan(self, text: str) -> Optional[TaskResult]:
        low = text.lower().strip()

        # Browser/document compound tasks
        if self._mentions_google_docs(low) and self._mentions_write_task(low):
            topic = self._extract_writing_topic(text)
            content = self._generate_document_text(topic)
            self.browser.open_google_docs()
            self._paste_into_web_document(content, wait_seconds=5.5)
            self.last_generated_text = content
            return TaskResult(True, "Opened Google Docs and wrote it.", "google_docs_write", {"text_preview": content[:1000]})

        if self._mentions_google_slides(low) and self._mentions_write_task(low):
            topic = self._extract_writing_topic(text)
            content = self.ai.chat([
                {"role": "system", "content": "Create concise slide content. Use a title, then 5-7 short bullet points. No markdown table."},
                {"role": "user", "content": topic},
            ], max_tokens=1000)
            self.browser.open_google_slides()
            self._paste_into_web_document(content, wait_seconds=5.5)
            self.last_generated_text = content
            return TaskResult(True, "Opened Google Slides and pasted slide content.", "google_slides_write", {"text_preview": content[:1000]})

        if ("open chrome" in low or "open browser" in low) and ("search for" in low or "google" in low):
            query = self._extract_search_query(text)
            if query:
                self.browser.search_google(query)
                return TaskResult(True, f"Searching Google for {query}.", "browser_search", {"query": query})

        if ("open youtube" in low or "youtube" in low) and "search" in low:
            query = self._after_phrase(text, "search for") or self._after_phrase(text, "search") or text
            query = re.sub(r"(?i)^.*?youtube\s*(for)?\s*", "", query).strip()
            self.browser.search_youtube(query)
            return TaskResult(True, f"Searching YouTube for {query}.", "youtube_search", {"query": query})

        # Local file compound tasks
        if self._mentions_create_file(low) and ("write" in low or "with" in low or "saying" in low):
            return self._create_and_write_file(text)

        if self._mentions_local_doc(low) and self._mentions_write_task(low):
            topic = self._extract_writing_topic(text)
            content = self._generate_document_text(topic)
            ext = "docx" if any(w in low for w in ["word", "docx", "document"]) else "txt"
            folder = self._extract_folder(low)
            name = self._extract_file_name(text) or self._name_from_topic(topic)
            if ext == "docx":
                path = self.files.create_docx(name, content, folder)
            else:
                path = self.files.create_txt(name, content, folder)
            self.last_created_file = path
            self.last_generated_text = content
            if "open" in low:
                self._open_path(path)
                return TaskResult(True, f"Created and opened {Path(path).name}.", "file_write_open", {"path": path})
            return TaskResult(True, f"Created {Path(path).name}.", "file_write", {"path": path})

        if low in ["open last file", "open the last file", "open created file", "open the created file"]:
            if not self.last_created_file:
                return TaskResult(True, "I do not have a created file saved in this session yet.", "file_open")
            self._open_path(self.last_created_file)
            return TaskResult(True, "Opened the last file I created.", "file_open", {"path": self.last_created_file})

        if low in ["paste last text", "paste last answer", "paste generated text", "paste it"] and self.last_generated_text:
            self.pc.paste_text(self.last_generated_text)
            return TaskResult(True, "Pasted it.", "paste_last")

        return None

    def _paste_into_web_document(self, content: str, wait_seconds: float = 5.0) -> None:
        # Give docs.new/slides.new enough time, then click the document body and paste.
        # The second paste is intentionally avoided; users can say "paste last text" if Google Docs was still loading.
        time.sleep(wait_seconds)
        try:
            screen_w, screen_h = pyautogui.size()
            pyautogui.click(screen_w // 2, int(screen_h * 0.42))
            time.sleep(0.4)
        except Exception:
            pass
        self.pc.paste_text(content)

    def _mentions_google_docs(self, low: str) -> bool:
        return "google docs" in low or "docs.new" in low or "google document" in low

    def _mentions_google_slides(self, low: str) -> bool:
        return "google slides" in low or "slides.new" in low

    def _mentions_local_doc(self, low: str) -> bool:
        return any(w in low for w in ["txt file", "text file", "word file", "word document", "docx", "document file"])

    def _mentions_create_file(self, low: str) -> bool:
        return any(low.startswith(p) for p in ["create txt", "create text", "create file", "create a file", "make txt", "make text", "make file", "make a file"])

    def _mentions_write_task(self, low: str) -> bool:
        return any(p in low for p in ["write", "essay", "article", "paragraph", "letter", "report", "summary", "cv", "resume"])

    def _extract_writing_topic(self, text: str) -> str:
        t = text.strip()
        patterns = [
            r"(?i).*?write\s+me\s+(.*)",
            r"(?i).*?write\s+(.*)",
            r"(?i).*?essay\s+about\s+(.*)",
            r"(?i).*?about\s+(.*)",
        ]
        for p in patterns:
            m = re.match(p, t)
            if m and m.group(1).strip():
                return m.group(1).strip()
        return t

    def _generate_document_text(self, topic: str) -> str:
        return self.ai.chat([
            {"role": "system", "content": "Write polished, ready-to-paste text. If the user asks for an essay, use a clear title, introduction, body paragraphs, and conclusion. Do not include meta commentary."},
            {"role": "user", "content": topic},
        ], max_tokens=2200)

    def _extract_search_query(self, text: str) -> str:
        return self._after_phrase(text, "search for") or self._after_phrase(text, "google") or self._after_phrase(text, "search") or ""

    def _after_phrase(self, text: str, phrase: str) -> str:
        idx = text.lower().find(phrase.lower())
        if idx == -1:
            return ""
        return text[idx + len(phrase):].strip(" :,-")

    def _create_and_write_file(self, text: str) -> TaskResult:
        low = text.lower()
        ext = "txt"
        if "word" in low or "docx" in low:
            ext = "docx"
        elif "powerpoint" in low or "presentation" in low or "pptx" in low:
            ext = "pptx"
        folder = self._extract_folder(low)
        name = self._extract_file_name(text) or "jarvis_file"
        content = self._extract_inline_content(text)
        if not content:
            topic = self._extract_writing_topic(text)
            content = self._generate_document_text(topic)
        if ext == "docx":
            path = self.files.create_docx(name, content, folder)
        elif ext == "pptx":
            path = self.files.create_pptx(name, content, folder)
        else:
            path = self.files.create_txt(name, content, folder)
        self.last_created_file = path
        self.last_generated_text = content
        if "open" in low:
            self._open_path(path)
            return TaskResult(True, f"Created and opened {Path(path).name}.", "file_create_open", {"path": path})
        return TaskResult(True, f"Created {Path(path).name}.", "file_create", {"path": path})

    def _extract_inline_content(self, text: str) -> str:
        for phrase in [" and write ", " with ", " saying ", " that says "]:
            if phrase in text.lower():
                idx = text.lower().find(phrase)
                return text[idx + len(phrase):].strip()
        return ""

    def _extract_file_name(self, text: str) -> str:
        m = re.search(r"(?i)(?:called|named|name it)\s+([^,]+?)(?:\s+with\s+|\s+and\s+write\s+|\s+saying\s+|$)", text)
        if m:
            return m.group(1).strip().strip('"\'')
        return ""

    def _extract_folder(self, low: str) -> Optional[str]:
        for folder in ["desktop", "downloads", "documents", "generated"]:
            if f" on my {folder}" in low or f" in {folder}" in low or f" to {folder}" in low:
                return folder
        return None

    def _name_from_topic(self, topic: str) -> str:
        words = re.sub(r"[^a-zA-Z0-9 ]+", "", topic).strip().split()
        return "_".join(words[:6]) or "jarvis_document"

    def _open_path(self, path: str) -> None:
        import os
        os.startfile(path)
