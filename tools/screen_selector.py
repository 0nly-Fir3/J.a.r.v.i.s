import json
import os
import subprocess
import sys
import time
from typing import List

import pyautogui

from .screen_reader import OCRBox, ScreenReader


class ScreenSelector:
    def __init__(self, reader: ScreenReader) -> None:
        self.reader = reader

    def highlight(self, query: str) -> str:
        text, boxes, path = self.reader.read_screen()
        matches = self.reader.find_text(query, boxes)
        if not matches:
            return f"I could not find '{query}' to highlight."
        payload = [self._box_dict(b) for b in matches[:8]]
        script = os.path.join(os.path.dirname(__file__), "highlight_overlay.py")
        subprocess.Popen([sys.executable, script, json.dumps(payload), "2500"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Highlighted {len(payload)} match(es) for '{query}'."

    def select_text(self, query: str) -> str:
        text, boxes, path = self.reader.read_screen()
        matches = self.reader.find_text(query, boxes)
        if not matches:
            return f"I could not find '{query}' to select."
        b = matches[0]
        pyautogui.moveTo(b.left, (b.top + b.bottom) // 2, duration=0.1)
        pyautogui.dragTo(b.right, (b.top + b.bottom) // 2, duration=0.25, button="left")
        return f"Selected '{b.text}'."

    def select_between(self, start: str, end: str) -> str:
        text, boxes, path = self.reader.read_screen()
        starts = self.reader.find_text(start, boxes)
        ends = self.reader.find_text(end, boxes)
        if not starts or not ends:
            return f"I could not find both '{start}' and '{end}'."
        a = starts[0]
        b = ends[-1]
        pyautogui.moveTo(a.left, (a.top + a.bottom) // 2, duration=0.1)
        pyautogui.dragTo(b.right, (b.top + b.bottom) // 2, duration=0.45, button="left")
        return f"Selected from '{a.text}' to '{b.text}'."

    def _box_dict(self, b: OCRBox) -> dict:
        return {"text": b.text, "left": b.left, "top": b.top, "right": b.right, "bottom": b.bottom}
