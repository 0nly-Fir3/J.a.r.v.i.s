import os
import shutil
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PIL import Image, ImageOps, ImageFilter

from .pc_control import PCControl


@dataclass
class OCRBox:
    text: str
    left: int
    top: int
    right: int
    bottom: int
    confidence: float

    @property
    def center(self) -> Tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)


@dataclass
class ScreenTarget:
    label: str
    left: int
    top: int
    right: int
    bottom: int
    confidence: float = 0.75

    @property
    def center(self) -> Tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)


class ScreenReader:
    def __init__(self) -> None:
        self.pc = PCControl()
        self.last_screenshot: Optional[str] = None
        self.last_boxes: List[OCRBox] = []
        self.last_targets: List[ScreenTarget] = []
        self.last_ocr_status: str = "OCR has not run yet."

    def capture(self) -> str:
        self.last_screenshot = self.pc.screenshot(temporary=True)
        return self.last_screenshot

    def read_screen(self) -> Tuple[str, List[OCRBox], str]:
        path = self.capture()
        boxes = self.ocr(path)
        self.last_boxes = boxes
        self.last_targets = self.detect_color_targets(path)
        text = self.boxes_to_text(boxes)
        if not text.strip():
            text = self.last_ocr_status or "Local OCR did not find readable text."
        return text, boxes, path

    def targets_status(self) -> str:
        parts = []
        if self.last_boxes:
            parts.append(f"OCR text boxes cached: {len(self.last_boxes)}")
        else:
            parts.append("OCR text boxes cached: 0")
        if self.last_targets:
            parts.append("Color targets cached:")
            for i, t in enumerate(self.last_targets[:20], 1):
                parts.append(f"{i}. {t.label} at {t.center}")
        else:
            parts.append("Color targets cached: 0")
        if self.last_screenshot:
            parts.append(f"Last internal screenshot: {self.last_screenshot}")
        return "\n".join(parts)

    def ocr_status(self) -> str:
        status = []
        try:
            import pytesseract  # noqa
            status.append("pytesseract Python package: installed")
        except Exception as e:
            status.append(f"pytesseract Python package: missing ({e})")

        cmd = self._tesseract_cmd()
        if cmd:
            status.append(f"Tesseract OCR engine: found at {cmd}")
        else:
            status.append("Tesseract OCR engine: NOT found. Install the Windows Tesseract app, not only the Python package.")
            status.append(r"Default expected path: C:\Program Files\Tesseract-OCR\tesseract.exe")
            status.append("After installing it, restart JARVIS.")
        status.append(f"Last OCR status: {self.last_ocr_status}")
        return "\n".join(status)

    def ocr(self, image_path: str) -> List[OCRBox]:
        self.last_ocr_status = "Starting OCR."
        boxes = self._pytesseract(image_path)
        if boxes:
            self.last_ocr_status = f"OCR working. Found {len(boxes)} text boxes."
            return boxes
        if "not found" not in self.last_ocr_status.lower():
            self.last_ocr_status = "OCR ran, but found no confident readable text."
        return []

    def boxes_to_text(self, boxes: List[OCRBox]) -> str:
        rows = sorted(boxes, key=lambda b: (b.top // 18, b.left))
        lines: List[str] = []
        current_y: Optional[int] = None
        current: List[str] = []
        for box in rows:
            y = box.top // 22
            if current_y is None:
                current_y = y
            if y != current_y:
                if current:
                    lines.append(" ".join(current))
                current = [box.text]
                current_y = y
            else:
                current.append(box.text)
        if current:
            lines.append(" ".join(current))
        return "\n".join(lines).strip()

    def find_text(self, query: str, boxes: Optional[List[OCRBox]] = None) -> List[OCRBox]:
        import difflib
        q = query.lower().strip()
        if boxes is None:
            if not self.last_boxes:
                _, boxes, _ = self.read_screen()
            else:
                boxes = self.last_boxes
        if not q:
            return []
        exact = [b for b in boxes if q in b.text.lower()]
        if exact:
            return exact
        phrase_matches = self._find_phrase(q, boxes)
        if phrase_matches:
            return phrase_matches
        matches: List[OCRBox] = []
        for b in boxes:
            ratio = difflib.SequenceMatcher(None, q, b.text.lower()).ratio()
            if ratio >= 0.65:
                matches.append(b)
        return sorted(matches, key=lambda b: b.confidence, reverse=True)

    def find_screen_target(self, query: str) -> Optional[ScreenTarget]:
        q = query.lower().strip()
        if not self.last_targets and self.last_screenshot:
            self.last_targets = self.detect_color_targets(self.last_screenshot)
        if not self.last_targets:
            path = self.capture()
            self.last_targets = self.detect_color_targets(path)
        color_words = ["blue", "red", "green", "yellow", "orange", "purple"]
        wanted = next((c for c in color_words if c in q), "")
        candidates = [t for t in self.last_targets if wanted and wanted in t.label]
        if not candidates and ("button" in q or "colored" in q):
            candidates = self.last_targets
        return candidates[0] if candidates else None

    def detect_color_targets(self, image_path: str) -> List[ScreenTarget]:
        try:
            img = Image.open(image_path).convert("RGB")
        except Exception:
            return []
        w, h = img.size
        max_w = 700
        scale = min(1.0, max_w / float(w))
        small = img.resize((int(w * scale), int(h * scale))) if scale < 1 else img
        sw, sh = small.size
        pix = small.load()
        visited = set()
        targets: List[ScreenTarget] = []

        def color_label(r: int, g: int, b: int) -> str:
            if b > 120 and b > r * 1.25 and b > g * 1.10:
                return "blue button"
            if r > 130 and r > g * 1.25 and r > b * 1.25:
                return "red button"
            if g > 120 and g > r * 1.15 and g > b * 1.15:
                return "green button"
            if r > 150 and g > 120 and b < 110:
                return "yellow button"
            if r > 150 and 70 < g < 150 and b < 120:
                return "orange button"
            if r > 120 and b > 120 and g < 130:
                return "purple button"
            return ""

        for y in range(0, sh, 3):
            for x in range(0, sw, 3):
                if (x, y) in visited:
                    continue
                label = color_label(*pix[x, y])
                if not label:
                    continue
                stack = [(x, y)]
                visited.add((x, y))
                xs, ys = [], []
                count = 0
                while stack and count < 5000:
                    cx, cy = stack.pop()
                    xs.append(cx); ys.append(cy); count += 1
                    for nx, ny in ((cx+3, cy), (cx-3, cy), (cx, cy+3), (cx, cy-3)):
                        if nx < 0 or ny < 0 or nx >= sw or ny >= sh or (nx, ny) in visited:
                            continue
                        if color_label(*pix[nx, ny]) == label:
                            visited.add((nx, ny))
                            stack.append((nx, ny))
                if count < 18:
                    continue
                left, right = min(xs), max(xs)
                top, bottom = min(ys), max(ys)
                bw, bh = right - left, bottom - top
                if bw < 18 or bh < 10 or bw > sw * 0.75 or bh > sh * 0.40:
                    continue
                inv = 1 / scale if scale else 1
                targets.append(ScreenTarget(label, int(left * inv), int(top * inv), int(right * inv), int(bottom * inv), 0.7))
        # Prefer targets near the center/top and remove near-duplicates.
        unique: List[ScreenTarget] = []
        for t in sorted(targets, key=lambda z: ((z.bottom - z.top) * (z.right - z.left)), reverse=True):
            if any(abs(t.center[0] - u.center[0]) < 30 and abs(t.center[1] - u.center[1]) < 30 for u in unique):
                continue
            unique.append(t)
        return unique[:25]

    def _find_phrase(self, q: str, boxes: List[OCRBox]) -> List[OCRBox]:
        words = q.split()
        if len(words) < 2:
            return []
        sorted_boxes = sorted(boxes, key=lambda b: (b.top // 25, b.left))
        for i in range(len(sorted_boxes)):
            combined = []
            left = top = 10**9
            right = bottom = 0
            conf = 0.0
            for b in sorted_boxes[i:i + len(words) + 3]:
                combined.append(b.text)
                left = min(left, b.left); top = min(top, b.top)
                right = max(right, b.right); bottom = max(bottom, b.bottom)
                conf += b.confidence
                phrase = " ".join(combined).lower()
                if q in phrase:
                    return [OCRBox(text=" ".join(combined), left=left, top=top, right=right, bottom=bottom, confidence=conf / max(1, len(combined)))]
        return []

    def _tesseract_cmd(self) -> Optional[str]:
        env_cmd = os.getenv("TESSERACT_CMD", "").strip().strip('"')
        candidates = []
        if env_cmd:
            candidates.append(env_cmd)
        candidates.extend([
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.join(os.path.expanduser("~"), r"AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        ])
        found = shutil.which("tesseract")
        if found:
            candidates.append(found)
        for c in candidates:
            if c and os.path.exists(c):
                return c
        return None

    def _prepare_for_ocr(self, image_path: str) -> Tuple[Image.Image, float]:
        original = Image.open(image_path).convert("RGB")
        w, h = original.size
        scale = 1.0
        img = original
        if w < 3000:
            img = original.resize((w * 2, h * 2))
            scale = 2.0
        gray = ImageOps.grayscale(img)
        gray = ImageOps.autocontrast(gray)
        gray = gray.filter(ImageFilter.SHARPEN)
        return gray, scale

    def _pytesseract(self, image_path: str) -> List[OCRBox]:
        try:
            import pytesseract
        except Exception as e:
            self.last_ocr_status = f"pytesseract Python package is not installed: {e}"
            return []

        cmd = self._tesseract_cmd()
        if not cmd:
            self.last_ocr_status = "Tesseract OCR engine not found. Install Tesseract for Windows or use screenshot and analyze."
            return []

        try:
            pytesseract.pytesseract.tesseract_cmd = cmd
            img, scale = self._prepare_for_ocr(image_path)
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config="--psm 6")
            boxes: List[OCRBox] = []
            for i, text in enumerate(data.get("text", [])):
                text = (text or "").strip()
                if not text:
                    continue
                try:
                    conf_raw = float(data["conf"][i])
                    conf = conf_raw / 100.0 if conf_raw > 1 else conf_raw
                except Exception:
                    conf = 0.5
                if conf < 0.20:
                    continue
                left = int(int(data["left"][i]) / scale)
                top = int(int(data["top"][i]) / scale)
                width = int(int(data["width"][i]) / scale)
                height = int(int(data["height"][i]) / scale)
                boxes.append(OCRBox(text=text, left=left, top=top, right=left + width, bottom=top + height, confidence=conf))
            return boxes
        except Exception as e:
            self.last_ocr_status = f"Tesseract OCR failed: {e}"
            return []
