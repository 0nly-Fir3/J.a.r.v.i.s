import os
import re
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openrouter_client import OpenRouterClient
from tools.action_history import ActionHistory
from tools.app_manager import AppManager
from tools.browser_controller import BrowserController
from tools.task_planner import TaskPlanner
from tools.file_creator import FileCreator
from tools.homework_reader import HomeworkReader
from tools.memory_manager import MemoryManager
from tools.pc_control import PCControl
from tools.screen_clicker import ScreenClicker
from tools.screen_reader import ScreenReader
from tools.screen_selector import ScreenSelector
from tools.window_manager import WindowManager
from tools.chrome_bridge import ChromeBridge
from tools.custom_commands import CustomCommandManager
from tools.file_indexer import FileIndexer
from tools.project_manager import ProjectManager
from tools.routine_manager import RoutineManager
from tools.windows_uia import WindowsUIAutomation
from tools.autopilot_agent import AutopilotAgent
from voice_normalizer import VoiceNormalizer


@dataclass
class RouteResult:
    reply: str
    handled: bool
    normalized: str
    action: str = "chat"
    extra: Optional[Dict[str, Any]] = None


class CommandRouter:
    def __init__(self) -> None:
        self.ai = OpenRouterClient()
        self.normalizer = VoiceNormalizer()
        self.memory = MemoryManager()
        self.history = ActionHistory()
        self.writing_mode = False
        self.pc = PCControl()
        self.apps = AppManager()
        self.browser = BrowserController("chrome")
        self.windows = WindowManager()
        self.screen = ScreenReader()
        self.clicker = ScreenClicker(self.screen)
        self.selector = ScreenSelector(self.screen)
        self.files = FileCreator()
        self.homework = HomeworkReader(self.screen)
        self.task_planner = TaskPlanner(self.ai, self.pc, self.apps, self.browser, self.files, self.windows)
        self.chrome = ChromeBridge()
        self.custom = CustomCommandManager()
        self.routines = RoutineManager()
        self.projects = ProjectManager()
        self.file_index = FileIndexer()
        self.uia = WindowsUIAutomation()
        self.autopilot = AutopilotAgent(self.ai)
        self.last_saved_file = ""
        self.silent_mode = os.getenv("JARVIS_SILENT_MODE", "false").lower() == "true"
        self.enable_shell = os.getenv("ENABLE_SHELL", "false").lower() == "true"
        self.enable_destructive = os.getenv("ENABLE_DESTRUCTIVE_ACTIONS", "false").lower() == "true"

    def _strip_wake_words(self, text: str) -> str:
        cleaned = (text or "").strip()
        low = cleaned.lower()
        for wake in ["hey jarvis", "ok jarvis", "jarvis", "hey service", "hey travis", "hey jervis"]:
            if low == wake:
                return ""
            if low.startswith(wake + " "):
                return cleaned[len(wake):].strip(" ,:-")
        return cleaned

    def _is_fast_local_command(self, text: str) -> bool:
        low = text.lower().strip()
        exact = {
            "chrome bridge status", "browser bridge status", "extension status",
            "reset chrome bridge", "clear chrome bridge", "clear chrome queue",
            "list chrome tabs", "show chrome tabs", "list tabs", "show tabs",
            "summarize this page", "summarize page", "read this page", "page summary",
            "list bookmarks", "show bookmarks", "new tab", "open new tab", "open a new tab",
            "close tab", "close current tab", "close most recent tab", "close the tab", "close this tab",
            "reopen tab", "reopen closed tab", "restore closed tab", "open closed tab",
            "next tab", "switch to next tab", "previous tab", "last tab", "switch to previous tab",
            "refresh", "refresh page", "reload", "reload page", "go back", "back", "go forward", "forward",
            "address bar", "click address bar", "select address bar",
        }
        if low in exact:
            return True
        if any(low.startswith(p) for p in ["switch to tab ", "open tab ", "click page ", "open bookmark "]):
            return True
        if low.startswith("open the ") and " bookmark" in low:
            return True
        return False

    def route(self, raw_text: str, source: str = "text") -> RouteResult:
        norm = self.normalizer.normalize(raw_text)
        text = self._strip_wake_words(norm.text)
        if not text:
            return self._record_result(raw_text, text, RouteResult("I did not hear anything.", True, text, "empty"))
        try:
            # Writing mode gets first chance, so dictation does not become a random chat response.
            writing = self._writing_mode_command(text)
            if writing is not None:
                return self._record_result(raw_text, text, writing)

            learned = self.custom.resolve(text)
            if learned and learned.lower() != text.lower():
                rr = self.route(learned, source="custom_command")
                rr.reply = f"Running custom command. {rr.reply}"
                return self._record_result(raw_text, text, rr)

            routine_steps = self.routines.match(text)
            if routine_steps:
                result = self._run_steps(routine_steps, label=text)
                return self._record_result(raw_text, text, result)

            # Browser bridge/status commands should never go through the AI planner.
            if self._is_fast_local_command(text):
                local = self._local_command(text)
                if local is not None:
                    return self._record_result(raw_text, text, local)

            task = self.task_planner.plan(text)
            if task is not None and task.handled:
                result = RouteResult(task.reply, True, text, task.action, task.extra or {})
                return self._record_result(raw_text, text, result)

            local = self._local_command(text)
            if local is not None:
                return self._record_result(raw_text, text, local)

            reply = self._chat(text)
            self.memory.add_history("user", text)
            self.memory.add_history("assistant", reply)
            return self._record_result(raw_text, text, RouteResult(reply=reply, handled=False, normalized=text, action="chat"))
        except Exception as e:
            reply = f"Command failed: {e}"
            return self._record_result(raw_text, text, RouteResult(reply=reply, handled=True, normalized=text, action="error"))

    def _record_result(self, raw: str, normalized: str, result: RouteResult) -> RouteResult:
        if self.silent_mode and result.action not in ["mode", "error", "interrupt"]:
            extra = result.extra or {}
            extra.setdefault("silent", True)
            result.extra = extra
        self.memory.log_command(raw, normalized, result.reply)
        self.history.log(raw, normalized, result.action, result.reply, result.extra or {})
        return result

    def _local_command(self, text: str) -> Optional[RouteResult]:
        low = text.lower().strip()

        teach = self.custom.teach_from_text(text)
        if teach:
            return RouteResult(teach, True, low, "custom_command")

        if low in ["silent mode", "be quiet", "quiet mode"]:
            self.silent_mode = True
            return RouteResult("Silent mode on.", True, low, "mode")

        if low in ["normal mode", "speak normally", "voice mode"]:
            self.silent_mode = False
            return RouteResult("Normal voice mode on.", True, low, "mode")

        if low in ["chrome bridge status", "browser bridge status", "extension status"]:
            st = self.chrome.status()
            if st.get("connected"):
                reply = f"Chrome bridge connected. Tabs: {st.get('tabs',0)}. Bookmarks: {st.get('bookmarks',0)}. Page: {st.get('page_title') or st.get('page_url') or 'no normal page snapshot yet'}."
            else:
                reply = "Chrome bridge is not connected yet. Keep JARVIS running, reload the patched extension, then open a normal website like google.com."
            return RouteResult(reply, True, low, "chrome_bridge", st)

        if low in ["reset chrome bridge", "clear chrome bridge", "clear chrome queue"]:
            n = self.chrome.clear_pending()
            return RouteResult(f"Chrome bridge queue cleared. Removed {n} old pending job(s).", True, low, "chrome_bridge")

        if low in ["summarize this page", "summarize page", "read this page", "page summary"]:
            self.chrome.request("snapshot", timeout=3.0)
            ctx = self.chrome.page_summary_context()
            reply = self.ai.chat([
                {"role": "system", "content": "Summarize the current webpage for the user. Be practical and concise."},
                {"role": "user", "content": ctx},
            ], max_tokens=900)
            return RouteResult(reply, True, low, "page_summary")

        if low in ["what am i looking at", "what am i seeing", "what is this", "explain this screen"]:
            chrome_ctx = self.chrome.page_summary_context()
            path = self.pc.screenshot(temporary=True)
            vision = self.ai.vision(path, "Explain what the user is looking at on this Windows screen. Mention the active app/page and the best next actions.", max_tokens=800)
            reply = self.ai.chat([
                {"role": "system", "content": "Combine browser context and vision analysis into a short useful answer."},
                {"role": "user", "content": f"Chrome/page context:\n{chrome_ctx[:6000]}\n\nVision analysis:\n{vision}"},
            ], max_tokens=900)
            return RouteResult(reply, True, low, "screen_explain", {"path": path})

        if low in ["fix this error", "why did this fail", "explain this error", "help me fix this error"]:
            path = self.pc.screenshot(temporary=True)
            screen_text, _, _ = self.screen.read_screen()
            vision = self.ai.vision(path, "Read the error/problem visible on screen and give a step-by-step fix. Do not say you cannot see the screen if image input works.", max_tokens=1000)
            reply = self.ai.chat([
                {"role": "system", "content": "You are a Windows/coding troubleshooting assistant. Give a direct fix plan."},
                {"role": "user", "content": f"OCR:\n{screen_text[:8000]}\n\nVision:\n{vision}"},
            ], max_tokens=1200)
            return RouteResult(reply, True, low, "fix_error", {"path": path})

        if low in ["list chrome tabs", "show chrome tabs", "list tabs", "show tabs"]:
            res = self.chrome.request("list_tabs", timeout=3.0)
            if res.get("ok") and res.get("tabs"):
                self.chrome.update_state({"tabs": res.get("tabs")})
            txt = self.chrome.list_tabs_text()
            if "do not have" in txt.lower() and res.get("error"):
                txt = "Chrome extension did not return tabs: " + res.get("error")
            return RouteResult(txt, True, low, "chrome_tabs", res)

        if low.startswith("switch to tab ") or low.startswith("open tab "):
            q = re.sub(r"^(switch to tab|open tab)\s+", "", text, flags=re.I).strip()
            res = self.chrome.request("switch_tab", {"query": q}, timeout=3.0)
            return RouteResult("Switched tab." if res.get("ok") else res.get("error", "Tab not found."), True, low, "chrome_tabs", res)

        if low.startswith("click page "):
            target = text[11:].strip()
            res = self.chrome.request("click_text", {"target": target}, timeout=3.0)
            return RouteResult(f"Clicked {target}." if res.get("ok") else res.get("error", "Could not click that on the page."), True, low, "chrome_click", res)

        if low in ["click first result", "open first result", "click the first result"]:
            res = self.chrome.request("click_text", {"target": "", "ordinal": 1}, timeout=3.0)
            return RouteResult("Clicked the first result." if res.get("ok") else res.get("error", "I could not click the first result."), True, low, "chrome_click", res)

        if low.startswith("create routine called ") and " with " in low:
            body = text[len("create routine called "):]
            name, steps = re.split(r"\s+with\s+", body, maxsplit=1, flags=re.I)
            return RouteResult(self.routines.save(name, steps), True, low, "routine")

        if low in ["list routines", "show routines"]:
            return RouteResult(self.routines.list(), True, low, "routine")

        if low in ["list custom commands", "show custom commands"]:
            return RouteResult(self.custom.list(), True, low, "custom_command")

        if low.startswith("switch to ") and low.endswith(" project"):
            name = re.sub(r"^switch to\s+|\s+project$", "", text, flags=re.I).strip()
            return RouteResult(self.projects.switch(name), True, low, "project")

        if low in ["project summary", "current project", "active project"]:
            return RouteResult(self.projects.summary(), True, low, "project")

        if low.startswith("save project note ") or low.startswith("add project note "):
            note = re.sub(r"^(save|add) project note\s+", "", text, flags=re.I).strip()
            return RouteResult(self.projects.add_note(note), True, low, "project")

        if low in ["rescan files", "index files", "update file index"]:
            return RouteResult(self.file_index.index(), True, low, "file_index")

        if low.startswith("find indexed file "):
            return RouteResult(self.file_index.find(text[18:]), True, low, "file_index")

        if low in ["open latest download", "open newest download", "open latest file"]:
            p = self.file_index.latest()
            if not p:
                return RouteResult("I could not find an indexed file. Say rescan files first.", True, low, "file_index")
            import os
            os.startfile(p)
            return RouteResult("Opened the latest indexed file.", True, low, "file_index", {"path": p})

        if low in ["ui automation status", "windows automation status"]:
            return RouteResult(self.uia.status(), True, low, "uia")

        if low.startswith("click ui ") or low.startswith("click windows "):
            target = re.sub(r"^click (ui|windows)\s+", "", text, flags=re.I).strip()
            return RouteResult(self.uia.click_control(target), True, low, "uia")

        if low in ["where did you save that", "where are the notes", "where did you save the notes", "show saved file location", "latest saved file"]:
            return self._saved_file_status()

        if low in ["open generated files", "open generated files folder", "open notes folder", "open jarvis notes folder"]:
            folder = str(Path("generated_files").resolve())
            Path(folder).mkdir(parents=True, exist_ok=True)
            os.startfile(folder)
            return RouteResult(f"Opened generated files folder: {folder}", True, low, "file_open", {"path": folder})

        if low in ["open latest generated file", "open latest notes", "open last saved file", "open saved notes"]:
            return self._open_latest_generated_file()

        if low.startswith("create txt file") or low.startswith("create text file") or low.startswith("create a txt file") or low.startswith("create a text file"):
            return self._create_quick_txt_command(text)

        if low.startswith("autopilot ") or low.startswith("research ") or low.startswith("do this task "):
            goal = re.sub(r"^(autopilot|research|do this task)\s+", "", text, flags=re.I).strip()
            if low.startswith("research ") or "make notes" in low or "create notes" in low or "write notes" in low or "save notes" in low:
                return self._research_notes_command(goal)
            steps = self.autopilot.plan(goal, self.chrome.page_summary_context())
            if not steps:
                return RouteResult("I could not create a safe autopilot plan for that.", True, low, "autopilot")
            return self._run_steps(steps, label="autopilot")

        if low in ["stop", "cancel", "interrupt", "stop talking"]:
            return RouteResult("Stopped.", True, low, "interrupt")

        if low in ["start writing mode", "writing mode", "dictation mode", "start dictation"]:
            self.writing_mode = True
            return RouteResult("Writing mode on.", True, low, "writing_mode")

        if low in ["stop writing mode", "exit writing mode", "end dictation", "stop dictation"]:
            self.writing_mode = False
            return RouteResult("Writing mode off.", True, low, "writing_mode")

        if low in ["undo", "undo that", "undo last action", "reverse that"]:
            return self._undo_last()

        if low in ["show command log", "command log", "recent commands", "debug log"]:
            return RouteResult(self.history.format_recent(12), True, low, "command_log")

        if low in ["clear command log", "clear debug log"]:
            return RouteResult(self.history.clear(), True, low, "command_log")

        if low in ["screenshot privacy", "screenshot status", "screen cache status"]:
            return RouteResult(self.pc.screenshot_privacy_status(), True, low, "screenshot_privacy")

        if low in ["clean screenshots", "delete internal screenshots", "clear screen cache"]:
            return RouteResult(self.pc.cleanup_internal_screenshots(), True, low, "screenshot_privacy")

        if low in ["screen targets", "show screen targets", "what can you click"]:
            return RouteResult(self.screen.targets_status(), True, low, "screen_targets")

        if low.startswith("remember that ") or low.startswith("remember "):
            item = re.sub(r"^remember( that)?\s+", "", text, flags=re.I).strip()
            return RouteResult(self.memory.remember(item), True, low, "memory")

        if low.startswith("forget "):
            item = re.sub(r"^forget\s+", "", text, flags=re.I).strip()
            return RouteResult(self.memory.forget(item), True, low, "memory")

        if low in ["what do you remember", "show memory", "show memories", "list memory", "list memories"]:
            return RouteResult(self.memory.list_memory(), True, low, "memory")

        if low in ["system info", "pc info", "computer info", "status report"]:
            return RouteResult(self.pc.system_info(), True, low, "system")

        if low in ["active window", "current window"]:
            return RouteResult(self.windows.active_window(), True, low, "window")

        if low in ["list windows", "show windows"]:
            return RouteResult(self.windows.list_windows(), True, low, "window")

        if low in ["new tab", "open new tab", "open a new tab"]:
            return RouteResult("Opened a new tab.", True, low, "browser", {"debug": self.browser.new_tab()})

        if low in ["close tab", "close current tab", "close most recent tab", "close the tab", "close this tab"]:
            debug = self.browser.close_tab()
            self.history.push_undo("browser_reopen_tab", "reopen closed tab")
            return RouteResult("Closed.", True, low, "browser", {"debug": debug})

        if low in ["reopen tab", "reopen closed tab", "restore closed tab", "open closed tab"]:
            return RouteResult("Reopened the last closed tab.", True, low, "browser", {"debug": self.browser.reopen_closed_tab()})

        if low in ["next tab", "switch to next tab"]:
            return RouteResult("Switched to the next tab.", True, low, "browser", {"debug": self.browser.next_tab()})

        if low in ["previous tab", "last tab", "switch to previous tab"]:
            return RouteResult("Switched to the previous tab.", True, low, "browser", {"debug": self.browser.previous_tab()})

        if low in ["refresh", "refresh page", "reload", "reload page"]:
            return RouteResult("Refreshed.", True, low, "browser", {"debug": self.browser.refresh()})

        if low in ["go back", "back"]:
            return RouteResult("Went back.", True, low, "browser", {"debug": self.browser.go_back()})

        if low in ["go forward", "forward"]:
            return RouteResult("Went forward.", True, low, "browser", {"debug": self.browser.go_forward()})

        if low in ["address bar", "click address bar", "select address bar"]:
            return RouteResult("Address bar selected.", True, low, "browser", {"debug": self.browser.address_bar()})

        if low in ["open google docs", "open docs", "new google doc", "create google doc"]:
            return RouteResult(self.browser.open_google_docs(), True, low, "browser")

        if low in ["open google sheets", "open sheets", "new google sheet"]:
            return RouteResult(self.browser.open_google_sheets(), True, low, "browser")

        if low in ["open google slides", "open slides", "new google slides"]:
            return RouteResult(self.browser.open_google_slides(), True, low, "browser")

        if low in ["list bookmarks", "show bookmarks"]:
            txt = self.chrome.list_bookmarks_text()
            if "do not have" not in txt.lower():
                return RouteResult(txt, True, low, "bookmarks")
            return RouteResult(self.browser.list_bookmarks(), True, low, "bookmarks")

        if low.startswith("open bookmark "):
            q = text[14:]
            res = self.chrome.request("open_bookmark", {"query": q}, timeout=3.0)
            if res.get("ok"):
                return RouteResult(f"Opened bookmark: {res.get('title','bookmark')}.", True, low, "bookmarks", res)
            return RouteResult(self.browser.open_bookmark(q), True, low, "bookmarks")

        if low.startswith("open the ") and " bookmark" in low:
            n = self.browser._ordinal_to_number(low)
            if n:
                res = self.chrome.request("open_bookmark", {"index": n}, timeout=3.0)
                if res.get("ok"):
                    return RouteResult(f"Opened bookmark {n}.", True, low, "bookmarks", res)
            return RouteResult(self.browser.open_bookmark(text), True, low, "bookmarks")

        if low.startswith("switch to "):
            return RouteResult(self.windows.switch_to(text[10:]), True, low, "window")

        if low in ["minimize", "minimize window", "minimize current window"]:
            return RouteResult(self.windows.minimize_current(), True, low, "window")

        if low in ["maximize", "maximize window", "maximize current window"]:
            return RouteResult(self.windows.maximize_current(), True, low, "window")

        if low in ["take screenshot", "screenshot", "take a screenshot"]:
            path = self.pc.screenshot()
            return RouteResult(f"Screenshot saved: {path}", True, low, "screenshot", {"path": path})

        if low in ["ocr status", "test ocr", "screen reader status"]:
            return RouteResult(self.screen.ocr_status(), True, low, "ocr_status")

        if low in ["test vision", "vision status", "test screenshot analysis"]:
            path = self.pc.screenshot(temporary=True)
            vision = self.ai.vision(path, "You are testing image input. Start your answer with VISION_OK if you can see the screenshot, then describe the screen in one short sentence. If you cannot see an image, say VISION_FAILED.", max_tokens=250)
            return RouteResult(f"Screenshot saved: {path}\n\n{vision}", True, low, "vision_test", {"path": path})

        if low in ["screenshot and analyze", "analyze screenshot", "analyze my screen", "screenshot analysis"]:
            path = self.pc.screenshot(temporary=True)
            analysis = self.ai.vision(path, "Analyze this Windows screenshot. Tell me what is visible, what app/page this seems to be, and any useful next actions. Keep it practical.")
            return RouteResult(f"Screenshot saved: {path}\n\n{analysis}", True, low, "vision", {"path": path})

        if low in ["read screen", "read my screen", "what is on my screen", "what's on my screen", "summarize screen", "summarize this page"]:
            screen_text, boxes, path = self.screen.read_screen()
            ocr_ok = bool(boxes) and "not found" not in screen_text.lower()
            if not ocr_ok or len(screen_text.strip()) < 80:
                vision_prompt = (
                    "You are JARVIS reading a Windows PC screen for the user. "
                    "Carefully describe what is visible. Read any important text you can see. "
                    "Mention likely clickable buttons or links. Do not talk about security limitations. "
                    "If you can see the screen, answer directly. Keep it concise but useful."
                )
                vision = self.ai.vision(path, vision_prompt, max_tokens=900)
                if "vision error" in vision.lower() or "request failed" in vision.lower() or "api key" in vision.lower():
                    msg = (
                        "I took a screenshot, but screen reading needs either local Tesseract OCR or a working OpenRouter vision model.\n\n"
                        f"Local OCR status: {screen_text}\n\n"
                        f"Vision response: {vision}\n\n"
                        "Try saying: ocr status\n"
                        "Also make sure OPENROUTER_VISION_MODEL in .env is an image/vision-capable model."
                    )
                    return RouteResult(msg, True, low, "screen_read", {"path": path, "ocr": screen_text})
                return RouteResult(f"I used screenshot analysis.\n\n{vision}", True, low, "screen_read", {"path": path, "ocr": screen_text})
            summary = self.ai.chat([
                {"role": "system", "content": "You summarize OCR text from a user's screen. Be concise and practical."},
                {"role": "user", "content": f"Screen OCR text:\n{screen_text}\n\nSummarize what is visible and mention likely clickable items."},
            ], max_tokens=600)
            return RouteResult(summary, True, low, "screen_read", {"path": path, "ocr": screen_text})

        if low.startswith("click "):
            target = self._strip_articles(text[6:])
            if target in ["", "mouse"]:
                return RouteResult(self.pc.click(), True, low, "mouse")
            return RouteResult(self.clicker.click_text(target), True, low, "screen_click")

        if low.startswith("press ") or low.startswith("tap "):
            verb_len = 6 if low.startswith("press ") else 4
            target = self._strip_articles(text[verb_len:])
            target_low = target.lower()
            visible_words = ["button", "link", "word", "result", "blue", "red", "green", "yellow", "orange", "purple", "that", "it", "first"]
            if any(w in target_low for w in visible_words):
                return RouteResult(self.clicker.click_text(target), True, low, "screen_click")

        if low.startswith("double click "):
            target = self._strip_articles(text[13:])
            if not target:
                return RouteResult(self.pc.double_click(), True, low, "mouse")
            return RouteResult(self.clicker.click_text(target, double=True), True, low, "screen_click")

        if low.startswith("right click "):
            target = self._strip_articles(text[12:])
            if not target:
                return RouteResult(self.pc.right_click(), True, low, "mouse")
            return RouteResult(self.clicker.click_text(target, right=True), True, low, "screen_click")

        if low in ["click", "left click"]:
            return RouteResult(self.pc.click(), True, low, "mouse")

        if low in ["right click"]:
            return RouteResult(self.pc.right_click(), True, low, "mouse")

        if low in ["double click"]:
            return RouteResult(self.pc.double_click(), True, low, "mouse")

        if low.startswith("move mouse to "):
            nums = re.findall(r"-?\d+", low)
            if len(nums) >= 2:
                return RouteResult(self.pc.move_mouse(int(nums[0]), int(nums[1])), True, low, "mouse")
            return RouteResult("Say it like: move mouse to 500 300.", True, low, "mouse")

        if low in ["scroll up"]:
            return RouteResult(self.pc.scroll(700), True, low, "mouse")

        if low in ["scroll down"]:
            return RouteResult(self.pc.scroll(-700), True, low, "mouse")

        if low.startswith("scroll up ") or low.startswith("scroll down "):
            amount = self._first_number(low, 700)
            sign = 1 if low.startswith("scroll up") else -1
            return RouteResult(self.pc.scroll(sign * amount), True, low, "mouse")

        if low.startswith("press "):
            return RouteResult(self.pc.press(text[6:]), True, low, "keyboard")

        if low.startswith("type text "):
            return RouteResult(self.pc.type_text(text[10:]), True, low, "keyboard")

        if low.startswith("type "):
            return RouteResult(self.pc.type_text(text[5:]), True, low, "keyboard")

        if low.startswith("paste text "):
            reply = self.pc.paste_text(text[11:])
            self.history.push_undo("restore_clipboard", "restore previous clipboard")
            return RouteResult(reply, True, low, "clipboard")

        if low.startswith("paste "):
            reply = self.pc.paste_text(text[6:])
            self.history.push_undo("restore_clipboard", "restore previous clipboard")
            return RouteResult(reply, True, low, "clipboard")

        if low in ["copy", "copy text", "copy selected text", "copy highlighted text"]:
            copied = self.pc.copy_selected()
            return RouteResult(f"Copied: {copied[:1000] if copied else 'nothing'}", True, low, "clipboard", {"clipboard": copied})

        if low in ["read clipboard", "what is in clipboard", "clipboard"]:
            return RouteResult(self.pc.read_clipboard(), True, low, "clipboard")

        if low.startswith("copy text "):
            return RouteResult(self.pc.set_clipboard(text[10:]), True, low, "clipboard")

        if low.startswith("highlight "):
            target = self._strip_articles(text[10:])
            return RouteResult(self.selector.highlight(target), True, low, "highlight")

        if low.startswith("select from ") and " to " in low:
            body = text[12:]
            start, end = body.split(" to ", 1)
            return RouteResult(self.selector.select_between(start.strip(' "\''), end.strip(' "\'')), True, low, "select")

        if low.startswith("select "):
            target = self._strip_articles(text[7:])
            return RouteResult(self.selector.select_text(target), True, low, "select")

        if low in ["make this better", "rewrite this", "improve this", "make selected text better", "rewrite selected text"]:
            selected = self.pc.copy_selected()
            if not selected.strip():
                return RouteResult("I could not copy any selected text.", True, low, "rewrite")
            improved = self.ai.chat([
                {"role": "system", "content": "Rewrite the user's selected text to be clearer, more natural, and more professional. Return only the rewritten text."},
                {"role": "user", "content": selected},
            ], max_tokens=900)
            self.pc.paste_text(improved)
            return RouteResult("I rewrote and replaced the selected text.", True, low, "rewrite", {"rewritten": improved})

        if low in ["rescan apps", "scan apps", "update apps"]:
            apps = self.apps.scan_apps()
            return RouteResult(f"Indexed {len(apps)} apps and shortcuts.", True, low, "apps")

        if low in ["list apps", "show apps"]:
            return RouteResult(self.apps.list_apps(), True, low, "apps")

        if low.startswith("open folder "):
            return RouteResult(self.pc.open_folder(text[12:]), True, low, "folder")

        if low.startswith("open "):
            target = text[5:].strip()
            folder_names = ["downloads", "download", "desktop", "documents", "pictures", "videos", "music"]
            if target.lower() in folder_names:
                return RouteResult(self.pc.open_folder(target), True, low, "folder")
            return RouteResult(self.apps.open_app(target), True, low, "apps")

        if low.startswith("close "):
            return RouteResult(self.apps.close_app(text[6:]), True, low, "apps")

        if low.startswith("go to "):
            return RouteResult(self.apps.open_url(text[6:]), True, low, "browser")

        if low.startswith("google "):
            return RouteResult(self.apps.google(text[7:]), True, low, "browser")

        if low.startswith("search google for "):
            return RouteResult(self.apps.google(text[18:]), True, low, "browser")

        if low.startswith("youtube "):
            return RouteResult(self.apps.youtube(text[8:]), True, low, "browser")

        if low.startswith("search youtube for "):
            return RouteResult(self.apps.youtube(text[19:]), True, low, "browser")

        if low.startswith("list files"):
            folder = "downloads"
            m = re.search(r"(?:in|from)\s+([a-zA-Z]+)", low)
            if m:
                folder = m.group(1)
            return RouteResult(self.pc.list_files(folder), True, low, "files")

        if low.startswith("find file "):
            return RouteResult(self.pc.find_file(text[10:]), True, low, "files")

        if low.startswith("create file ") or low.startswith("create a file ") or low.startswith("make file ") or low.startswith("make a file "):
            return self._create_file_command(text)

        if low.startswith("write me ") or low.startswith("write an ") or low.startswith("write a "):
            return self._writing_command(text)

        if low.startswith("read file "):
            content, label = self.homework.read_file(text[10:])
            if not content:
                return RouteResult(label, True, low, "homework")
            summary = self.ai.chat([
                {"role": "system", "content": "Summarize the file for the user. If it looks like homework, explain what the task asks for and suggest how to answer."},
                {"role": "user", "content": f"File: {label}\n\n{content[:12000]}"},
            ], max_tokens=1000)
            return RouteResult(summary, True, low, "homework", {"file": label})

        if low in ["read my homework", "do my homework", "help with homework", "answer my homework"]:
            p = self.homework.find_latest_homework("")
            if not p:
                screen_text, _, path = self.screen.read_screen()
                if screen_text:
                    response = self.ai.chat([
                        {"role": "system", "content": "Help the user understand and answer homework visible on screen. Show reasoning and a usable draft answer."},
                        {"role": "user", "content": screen_text[:12000]},
                    ], max_tokens=1400)
                    return RouteResult(response, True, low, "homework", {"screen": path})
                return RouteResult("I could not find a recent homework file. Open the homework on screen and say 'read screen'.", True, low, "homework")
            content, label = self.homework.read_file(str(p))
            response = self.ai.chat([
                {"role": "system", "content": "Help the user with homework. Explain the task, then provide a clear draft answer the user can learn from."},
                {"role": "user", "content": f"Homework file: {label}\n\n{content[:14000]}"},
            ], max_tokens=1600)
            return RouteResult(response, True, low, "homework", {"file": label})

        if low.startswith("run command "):
            return self._shell_command(text[12:])

        return None

    def _writing_mode_command(self, text: str) -> Optional[RouteResult]:
        low = text.lower().strip()
        if not self.writing_mode:
            return None

        # Commands must be checked before dictation, otherwise "stop writing mode" gets typed.
        stop_cmds = ["stop writing mode", "exit writing mode", "end dictation", "stop dictation", "stop writing", "stop"]
        pause_cmds = ["pause writing", "pause dictation", "pause writing mode"]
        resume_cmds = ["resume writing", "resume dictation", "continue writing"]
        if low in stop_cmds:
            self.writing_mode = False
            return RouteResult("Writing mode off.", True, low, "writing_mode")
        if low in pause_cmds:
            self.writing_mode = False
            return RouteResult("Writing paused.", True, low, "writing_mode")
        if low in resume_cmds:
            self.writing_mode = True
            return RouteResult("Writing resumed.", True, low, "writing_mode")

        if low.startswith("jarvis command ") or low.startswith("command "):
            cmd = re.sub(r"^(jarvis command|command)\s+", "", text, flags=re.I).strip()
            old = self.writing_mode
            self.writing_mode = False
            result = self.route(cmd, source="writing_command")
            self.writing_mode = old
            return RouteResult(result.reply, True, low, "writing_command", result.extra or {})

        if low in ["new paragraph", "next paragraph"]:
            self.pc.paste_text("\n\n")
            self.history.push_undo("restore_clipboard", "restore previous clipboard")
            return RouteResult("New paragraph.", True, low, "writing_mode", {"silent": True})
        if low in ["new line", "next line"]:
            self.pc.paste_text("\n")
            self.history.push_undo("restore_clipboard", "restore previous clipboard")
            return RouteResult("New line.", True, low, "writing_mode", {"silent": True})
        if low in ["delete last word"]:
            self.pc.press("ctrl backspace")
            return RouteResult("Deleted last word.", True, low, "writing_mode")
        if low in ["delete last sentence", "delete last line"]:
            self.pc.press("shift home")
            self.pc.press("backspace")
            return RouteResult("Deleted the last line.", True, low, "writing_mode")
        if low in ["make that better", "rewrite last sentence", "improve that", "make it better"]:
            selected = self.pc.copy_selected()
            if not selected.strip():
                return RouteResult("Select the text first, then say make that better.", True, low, "writing_mode")
            improved = self.ai.chat([
                {"role": "system", "content": "Rewrite the selected text to be clearer and more professional. Return only the rewritten text."},
                {"role": "user", "content": selected},
            ], max_tokens=700)
            self.pc.paste_text(improved)
            return RouteResult("Improved it.", True, low, "writing_mode")

        if low.startswith("write this "):
            content = text[11:].strip()
        elif low.startswith("write "):
            content = text[6:].strip()
        elif low.startswith("type "):
            content = text[5:].strip()
        elif low.startswith("paste "):
            content = text[6:].strip()
        else:
            content = text.strip()
        content = self._dictation_format(content)
        if not content:
            return RouteResult("Writing mode is on. Say the text you want me to write.", True, low, "writing_mode")
        self.pc.paste_text(content)
        self.history.push_undo("restore_clipboard", "restore previous clipboard")
        return RouteResult("Written.", True, low, "writing_mode", {"silent": True})

    def _dictation_format(self, content: str) -> str:
        replacements = {
            " new paragraph ": "\n\n",
            " new line ": "\n",
            " comma": ",",
            " period": ".",
            " full stop": ".",
            " question mark": "?",
            " exclamation mark": "!",
            " colon": ":",
            " semicolon": ";",
            " open quote": "\"",
            " close quote": "\"",
        }
        text = " " + content.strip() + " "
        for k, v in replacements.items():
            text = text.replace(k, v + (" " if v not in ["\n", "\n\n"] else ""))
        text = re.sub(r"\s+([,\.\?\!;:])", r"\1", text)
        return text.strip()

    def _run_steps(self, steps: List[str], label: str = "routine") -> RouteResult:
        replies = []
        for step in steps[:8]:
            result = self.route(step, source=label)
            replies.append(f"{step} -> {result.reply}")
        return RouteResult(f"Done. Ran {min(len(steps),8)} step(s).", True, label, label, {"steps": replies})

    def _undo_last(self) -> RouteResult:
        item = self.history.pop_undo()
        if not item:
            return RouteResult("Nothing to undo yet.", True, "undo", "undo")
        kind = item.get("kind")
        if kind == "browser_reopen_tab":
            self.browser.reopen_closed_tab()
            return RouteResult("Undone. Reopened the tab.", True, "undo", "undo")
        if kind == "restore_clipboard":
            self.pc.restore_previous_clipboard()
            return RouteResult("Undone. I restored the previous clipboard.", True, "undo", "undo")
        return RouteResult(f"I remembered the last undo action, but I cannot reverse {kind} yet.", True, "undo", "undo")

    def _chat(self, text: str) -> str:
        system = (
            "You are JARVIS V10, a concise Windows personal OS assistant. "
            "The Python backend handles local PC commands, browser control, files, routines, memory, and screen reading. "
            "For normal conversation, answer naturally. If the user asks for an action that should be done locally, tell them the exact voice command to use."
        )
        memory_context = self.memory.context()
        messages: List[Dict[str, str]] = [{"role": "system", "content": system + ("\n" + memory_context if memory_context else "")}]
        messages.extend(self.memory.recent_history(10))
        messages.append({"role": "user", "content": text})
        return self.ai.chat(messages)

    def _latest_generated_path(self) -> Optional[Path]:
        folder = Path("generated_files")
        folder.mkdir(parents=True, exist_ok=True)
        files = [p for p in folder.glob("*") if p.is_file()]
        if not files:
            return None
        return max(files, key=lambda p: p.stat().st_mtime)

    def _saved_file_status(self) -> RouteResult:
        path = Path(self.last_saved_file) if self.last_saved_file else self._latest_generated_path()
        if not path or not path.exists():
            folder = str(Path("generated_files").resolve())
            return RouteResult(f"I do not have a saved file yet. Generated files will be stored here: {folder}", True, "where saved", "file_status", {"folder": folder})
        return RouteResult(f"Latest saved file:\n{path.resolve()}", True, "where saved", "file_status", {"path": str(path.resolve())})

    def _open_latest_generated_file(self) -> RouteResult:
        path = Path(self.last_saved_file) if self.last_saved_file else self._latest_generated_path()
        if not path or not path.exists():
            return RouteResult("I could not find a generated file yet.", True, "open latest generated file", "file_open")
        os.startfile(str(path.resolve()))
        return RouteResult(f"Opened latest saved file: {path.resolve()}", True, "open latest generated file", "file_open", {"path": str(path.resolve())})

    def _create_quick_txt_command(self, text: str) -> RouteResult:
        low = text.lower()
        name = "jarvis_note"
        m = re.search(r"called\s+(.+?)(?:\s+and\s+open|\s+open it|\s+and\s+write|\s+write|\s+with|$)", text, re.I)
        if m and m.group(1).strip():
            name = m.group(1).strip()
        content = "Created by JARVIS."
        for pat in [r"open it and write\s+(.+)$", r"and write\s+(.+)$", r"write\s+(.+)$", r"with\s+(.+)$", r"saying\s+(.+)$"]:
            m2 = re.search(pat, text, re.I)
            if m2:
                content = m2.group(1).strip()
                break
        path = self.files.create_txt(name, content, "generated")
        self.last_saved_file = path
        if "open it" in low or "and open" in low or "open the file" in low:
            os.startfile(path)
            return RouteResult(f"Created and opened the text file:\n{path}", True, low, "file_create", {"path": path})
        return RouteResult(f"Created the text file:\n{path}", True, low, "file_create", {"path": path})

    def _research_notes_command(self, goal: str) -> RouteResult:
        raw_goal = goal.strip()
        raw_goal = re.sub(r"^(research|about)\s+", "", raw_goal, flags=re.I).strip()
        raw_goal = re.sub(r"\s+and\s+(make|create|write|save)\s+(research\s+)?notes.*$", "", raw_goal, flags=re.I).strip()
        raw_goal = re.sub(r"\s+with\s+notes.*$", "", raw_goal, flags=re.I).strip()
        if not raw_goal:
            return RouteResult("Tell me what topic you want me to research.", True, "research", "autopilot")
        self.apps.google(raw_goal)
        time.sleep(1.0)
        snap = self.chrome.request("snapshot", timeout=2.5)
        ctx = self.chrome.page_summary_context()
        snapshot_text = ""
        if isinstance(snap, dict) and snap.get("ok"):
            snapshot_text = (snap.get("text") or "")[:8000]
            elements = snap.get("elements") or []
            if elements:
                labels = [str(e.get("label", ""))[:160] for e in elements[:40] if e.get("label")]
                if labels:
                    snapshot_text += "\n\nVisible page elements:\n" + "\n".join(labels)
        source_context = (snapshot_text or ctx or "No live page text available yet.")[:12000]
        notes = self.ai.chat([
            {"role": "system", "content": "Create practical research notes for the user. Use the provided browser/search context if available. If context is weak, be honest and create a useful starter note with search terms, what to compare, and next steps. Keep it organized with headings and bullets."},
            {"role": "user", "content": f"Research topic: {raw_goal}\n\nBrowser/search context:\n{source_context}"},
        ], max_tokens=1400)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        safe_topic = re.sub(r"[^a-zA-Z0-9]+", "_", raw_goal).strip("_")[:45] or "research"
        content = f"Research Notes: {raw_goal}\nSaved: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{notes}\n"
        path = self.files.create_txt(f"research_notes_{safe_topic}_{stamp}", content, "generated")
        self.last_saved_file = path
        try:
            os.startfile(path)
        except Exception:
            pass
        return RouteResult(f"I searched Google and saved the notes here:\n{path}\n\nI opened the notes file.", True, "research", "autopilot", {"path": path, "topic": raw_goal})

    def _create_file_command(self, text: str) -> RouteResult:
        low = text.lower()
        ext = ".txt"
        if "word" in low or "docx" in low:
            ext = ".docx"
        if "powerpoint" in low or "presentation" in low or "pptx" in low:
            ext = ".pptx"
        folder = None
        for candidate in ["desktop", "downloads", "documents", "generated"]:
            if f" on my {candidate}" in low or f" in {candidate}" in low:
                folder = candidate
        name = "jarvis_file"
        m = re.search(r"called\s+([\w\- åäöÅÄÖ\.]+)", text, re.I)
        if m:
            name = m.group(1).strip()
        content = ""
        if " with " in low:
            content = text.split(" with ", 1)[1].strip()
        elif " saying " in low:
            content = text.split(" saying ", 1)[1].strip()
        if not content:
            content = "Created by JARVIS."
        if ext == ".docx":
            path = self.files.create_docx(name, content, folder)
        elif ext == ".pptx":
            path = self.files.create_pptx(name, content, folder)
        else:
            path = self.files.create_txt(name, content, folder)
        self.last_saved_file = path
        return RouteResult(f"Created file: {path}", True, low, "file_create", {"path": path})

    def _writing_command(self, text: str) -> RouteResult:
        low = text.lower()
        wants_docx = "word" in low or "docx" in low or "document" in low or "save" in low
        wants_pptx = "powerpoint" in low or "presentation" in low or "slides" in low
        prompt = text
        if wants_pptx:
            system = "Create slide content. Separate slides with a line containing only ---. Use a title line then short bullet lines."
        else:
            system = "Write a high quality response for the user's request. Be clear, useful, and ready to paste into a document."
        content = self.ai.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ], max_tokens=1800)
        if wants_pptx:
            path = self.files.create_pptx("jarvis_presentation", content, "generated")
            self.last_saved_file = path
            return RouteResult(f"Created presentation: {path}\n\n{content[:1200]}", True, low, "file_create", {"path": path})
        if wants_docx:
            path = self.files.create_docx("jarvis_document", content, "generated")
            self.last_saved_file = path
            return RouteResult(f"Created Word document: {path}\n\n{content[:1200]}", True, low, "file_create", {"path": path})
        return RouteResult(content, True, low, "writing")

    def _shell_command(self, cmd: str) -> RouteResult:
        if not self.enable_shell:
            return RouteResult("Shell commands are disabled. Set ENABLE_SHELL=true in .env and restart if you want this.", True, "run command", "shell")
        blocked = ["format ", "del /f", "rd /s", "rmdir /s", "shutdown", "cipher /w", "diskpart", "bcdedit", "reg delete"]
        if any(b in cmd.lower() for b in blocked) and not self.enable_destructive:
            return RouteResult("I blocked that command because it looks destructive. Set ENABLE_DESTRUCTIVE_ACTIONS=true only if you fully understand the risk.", True, "run command", "shell")
        completed = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=30)
        out = (completed.stdout + "\n" + completed.stderr).strip()
        return RouteResult(out[:4000] if out else "Command completed with no output.", True, "run command", "shell")

    def _strip_articles(self, text: str) -> str:
        text = text.strip()
        text = re.sub(r"^(the|a|an)\s+", "", text, flags=re.I)
        text = re.sub(r"\b(button|link|word|phrase|text)\b", "", text, flags=re.I).strip()
        return text

    def _first_number(self, text: str, default: int) -> int:
        nums = re.findall(r"\d+", text)
        return int(nums[0]) if nums else default
