
from typing import Optional


class WindowsUIAutomation:
    def __init__(self) -> None:
        self.available = False
        self.error = ""
        try:
            import pywinauto  # noqa
            self.available = True
        except Exception as e:
            self.error = str(e)

    def status(self) -> str:
        if self.available:
            return "Windows UI Automation is available."
        return "Windows UI Automation is not available. Optional package pywinauto may not be installed."

    def click_control(self, name: str) -> str:
        if not self.available:
            return self.status()
        try:
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")
            win = desktop.get_active()
            target = None
            name_low = name.lower().strip()
            for ctrl in win.descendants():
                try:
                    label = (ctrl.window_text() or "").strip()
                    if label and name_low in label.lower():
                        target = ctrl
                        break
                except Exception:
                    pass
            if not target:
                return f"I could not find a Windows UI element named {name}."
            target.click_input()
            return f"Clicked {name}."
        except Exception as e:
            return f"UI Automation failed: {e}"
