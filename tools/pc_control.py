import os
import platform
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import psutil
import pyautogui
import pyperclip

pyautogui.FAILSAFE = True


def safe_name(name: str) -> str:
    keep = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ ."
    cleaned = "".join(c for c in name if c in keep).strip()
    return cleaned or "file"


class PCControl:
    def __init__(self) -> None:
        self.screenshot_dir = Path("screenshots")
        self.screen_cache_dir = Path("data") / "screen_cache"
        self.screenshot_dir.mkdir(exist_ok=True)
        self.screen_cache_dir.mkdir(parents=True, exist_ok=True)
        self.last_clipboard_before_paste = ""

    def screenshot(self, temporary: bool = False) -> str:
        """Take a screenshot.

        Manual screenshots are kept in ./screenshots. Internal screenshots used for OCR,
        vision, and target detection go to ./data/screen_cache and are automatically
        cleaned up after SCREENSHOT_RETENTION_MINUTES unless KEEP_INTERNAL_SCREENSHOTS=true.
        """
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        folder = self.screen_cache_dir if temporary else self.screenshot_dir
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"screenshot_{stamp}.png"
        img = pyautogui.screenshot()
        img.save(path)
        if temporary:
            self.cleanup_internal_screenshots()
        return str(path.resolve())

    def cleanup_internal_screenshots(self) -> str:
        keep = os.getenv("KEEP_INTERNAL_SCREENSHOTS", "false").lower() == "true"
        if keep:
            return "Internal screenshots are being kept because KEEP_INTERNAL_SCREENSHOTS=true."
        try:
            minutes = int(os.getenv("SCREENSHOT_RETENTION_MINUTES", "15"))
        except ValueError:
            minutes = 15
        cutoff = time.time() - max(minutes, 1) * 60
        removed = 0
        for p in self.screen_cache_dir.glob("*.png"):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
            except Exception:
                pass
        return f"Removed {removed} old internal screenshot(s)."

    def screenshot_privacy_status(self) -> str:
        keep = os.getenv("KEEP_INTERNAL_SCREENSHOTS", "false").lower() == "true"
        minutes = os.getenv("SCREENSHOT_RETENTION_MINUTES", "15")
        cache_count = len(list(self.screen_cache_dir.glob("*.png"))) if self.screen_cache_dir.exists() else 0
        manual_count = len(list(self.screenshot_dir.glob("*.png"))) if self.screenshot_dir.exists() else 0
        mode = "keeping internal screenshots" if keep else f"auto-deleting internal screenshots older than {minutes} minute(s)"
        return (
            f"Screenshot privacy: {mode}.\n"
            f"Internal screen cache files: {cache_count}.\n"
            f"Manual saved screenshots: {manual_count}.\n"
            "Screen commands still work because JARVIS stores OCR boxes and target coordinates, not only image files."
        )

    def click(self, button: str = "left") -> str:
        pyautogui.click(button=button)
        return f"Clicked {button}."

    def double_click(self) -> str:
        pyautogui.doubleClick()
        return "Double clicked."

    def right_click(self) -> str:
        pyautogui.rightClick()
        return "Right clicked."

    def move_mouse(self, x: int, y: int) -> str:
        pyautogui.moveTo(x, y, duration=0.15)
        return f"Moved mouse to {x}, {y}."

    def scroll(self, amount: int) -> str:
        pyautogui.scroll(amount)
        return "Scrolled up." if amount > 0 else "Scrolled down."

    def press(self, keys: str) -> str:
        cleaned = keys.lower().replace("windows", "win").replace("control", "ctrl")
        parts = [p.strip() for p in cleaned.replace("+", " ").split() if p.strip()]
        if not parts:
            return "No key was provided."
        if len(parts) == 1:
            pyautogui.press(parts[0])
        else:
            pyautogui.hotkey(*parts)
        return f"Pressed {' + '.join(parts)}."

    def type_text(self, text: str) -> str:
        pyautogui.write(text, interval=0.002)
        return "Typed the text."

    def paste_text(self, text: str) -> str:
        self.last_clipboard_before_paste = pyperclip.paste() or ""
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        return "Pasted the text."

    def restore_previous_clipboard(self) -> str:
        pyperclip.copy(self.last_clipboard_before_paste or "")
        return "Restored previous clipboard text."

    def copy_selected(self) -> str:
        pyautogui.hotkey("ctrl", "c")
        return pyperclip.paste()

    def read_clipboard(self) -> str:
        return pyperclip.paste() or "Clipboard is empty."

    def set_clipboard(self, text: str) -> str:
        pyperclip.copy(text)
        return "Copied text to clipboard."

    def system_info(self) -> str:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(Path.home()))
        battery = psutil.sensors_battery()
        battery_text = "No battery detected" if battery is None else f"{battery.percent}% battery, plugged in: {battery.power_plugged}"
        return (
            f"System: {platform.system()} {platform.release()}\n"
            f"PC name: {platform.node()}\n"
            f"CPU usage: {cpu}%\n"
            f"RAM: {round(mem.used / 1024**3, 2)} GB used of {round(mem.total / 1024**3, 2)} GB\n"
            f"Disk: {round(disk.used / 1024**3, 2)} GB used of {round(disk.total / 1024**3, 2)} GB\n"
            f"Power: {battery_text}"
        )

    def list_files(self, folder_name: str, limit: int = 30) -> str:
        folder = self._folder(folder_name)
        if not folder.exists():
            return f"Folder not found: {folder}"
        rows = sorted(folder.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        if not rows:
            return f"No files found in {folder}."
        return "\n".join(f"{p.name}{'/' if p.is_dir() else ''}" for p in rows)

    def find_file(self, query: str, limit: int = 20) -> str:
        query = query.lower().strip()
        bases = [Path.home() / "Desktop", Path.home() / "Downloads", Path.home() / "Documents"]
        results: List[str] = []
        for base in bases:
            if not base.exists():
                continue
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for name in files + dirs:
                    if query in name.lower():
                        results.append(str(Path(root) / name))
                        if len(results) >= limit:
                            return "\n".join(results)
        return "No matching files found."

    def open_folder(self, folder_name: str) -> str:
        folder = self._folder(folder_name)
        if not folder.exists():
            return f"Folder not found: {folder}"
        os.startfile(str(folder)) if hasattr(os, "startfile") else subprocess.Popen(["xdg-open", str(folder)])
        return f"Opened {folder.name}."

    def _folder(self, name: str) -> Path:
        key = name.lower().strip()
        home = Path.home()
        mapping: Dict[str, Path] = {
            "desktop": home / "Desktop",
            "downloads": home / "Downloads",
            "download": home / "Downloads",
            "documents": home / "Documents",
            "document": home / "Documents",
            "pictures": home / "Pictures",
            "videos": home / "Videos",
            "music": home / "Music",
            "home": home,
        }
        return mapping.get(key, home / key)
