import pyautogui

from .screen_reader import ScreenReader


class ScreenClicker:
    def __init__(self, reader: ScreenReader) -> None:
        self.reader = reader
        self.last_clicked = ""

    def click_text(self, query: str, double: bool = False, right: bool = False) -> str:
        q = (query or "").strip().lower()
        if q in ["it", "that", "this", "first one", "first result", "first item"]:
            return self.click_first_target(double=double, right=right)

        color_target = self.reader.find_screen_target(q)
        if color_target and any(word in q for word in ["blue", "red", "green", "yellow", "orange", "purple", "button", "colored"]):
            x, y = color_target.center
            pyautogui.moveTo(x, y, duration=0.15)
            self._perform_click(double, right)
            self.last_clicked = color_target.label
            return f"Clicked the {color_target.label}."

        boxes = self.reader.last_boxes
        matches = self.reader.find_text(query, boxes) if boxes else []
        if not matches:
            _, boxes, _ = self.reader.read_screen()
            matches = self.reader.find_text(query, boxes)
        if not matches:
            return f"I could not find '{query}' on the screen. Try saying 'read screen' first, then click the exact word."
        box = matches[0]
        x, y = box.center
        pyautogui.moveTo(x, y, duration=0.15)
        self._perform_click(double, right)
        self.last_clicked = box.text
        if right:
            return f"Right clicked {box.text}."
        if double:
            return f"Double clicked {box.text}."
        return f"Clicked {box.text}."

    def click_first_target(self, double: bool = False, right: bool = False) -> str:
        if not self.reader.last_boxes and not self.reader.last_targets:
            self.reader.read_screen()
        if self.reader.last_boxes:
            # Prefer text in the upper/middle screen that looks like a button/link/result.
            box = sorted(self.reader.last_boxes, key=lambda b: (b.top, b.left))[0]
            x, y = box.center
            pyautogui.moveTo(x, y, duration=0.15)
            self._perform_click(double, right)
            self.last_clicked = box.text
            return f"Clicked {box.text}."
        if self.reader.last_targets:
            target = self.reader.last_targets[0]
            x, y = target.center
            pyautogui.moveTo(x, y, duration=0.15)
            self._perform_click(double, right)
            self.last_clicked = target.label
            return f"Clicked the {target.label}."
        return "I do not have a screen target yet. Say 'read screen' first."

    def _perform_click(self, double: bool, right: bool) -> None:
        if right:
            pyautogui.rightClick()
        elif double:
            pyautogui.doubleClick()
        else:
            pyautogui.click()
