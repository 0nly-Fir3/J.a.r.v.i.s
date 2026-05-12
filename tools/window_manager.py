from typing import List

try:
    import pygetwindow as gw
except Exception:
    gw = None


class WindowManager:
    def active_window(self) -> str:
        if gw is None:
            return "Window control is not available on this system."
        w = gw.getActiveWindow()
        return w.title if w else "No active window detected."

    def list_windows(self) -> str:
        if gw is None:
            return "Window control is not available on this system."
        titles: List[str] = [w.title for w in gw.getAllWindows() if w.title]
        return "\n".join(titles[:40]) if titles else "No windows found."

    def switch_to(self, name: str) -> str:
        if gw is None:
            return "Window control is not available on this system."
        name = name.lower().strip()
        for w in gw.getAllWindows():
            if w.title and name in w.title.lower():
                try:
                    if w.isMinimized:
                        w.restore()
                    w.activate()
                    return f"Switched to {w.title}."
                except Exception as e:
                    return f"Found the window but could not activate it: {e}"
        return f"No window found matching {name}."

    def minimize_current(self) -> str:
        if gw is None:
            return "Window control is not available."
        w = gw.getActiveWindow()
        if not w:
            return "No active window found."
        w.minimize()
        return "Minimized the current window."

    def maximize_current(self) -> str:
        if gw is None:
            return "Window control is not available."
        w = gw.getActiveWindow()
        if not w:
            return "No active window found."
        w.maximize()
        return "Maximized the current window."
