import difflib
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class NormalizedCommand:
    original: str
    text: str
    confidence: float
    changed: bool
    reason: str


class VoiceNormalizer:
    def __init__(self) -> None:
        self.phrase_replacements: Dict[str, str] = {
            "auto pilot": "autopilot",
            "make nodes": "make notes",
            "make note": "make notes",
            "create nodes": "create notes",
            "right notes": "write notes",
            "write nodes": "write notes",
            "safe notes": "save notes",
            "stick dress": "stick drift",
            "strict drift": "stick drift",
            "stick driven": "stick drift",
            "stick drifting": "stick drift",
            "anti strict drift": "anti stick drift",
            "anti stick driven": "anti stick drift",
            "anti stick dress": "anti stick drift",
            "budget and the stick drift": "budget anti stick drift",
            "open latest note": "open latest notes",
            "where are my nodes": "where are the notes",
            "where are my notes": "where are the notes",
            "face text": "paste text",
            "phase text": "paste text",
            "pays text": "paste text",
            "paced text": "paste text",
            "based text": "paste text",
            "peace text": "paste text",
            "paste tax": "paste text",
            "pasta text": "paste text",
            "piece text": "paste text",
            "taste text": "paste text",
            "type tax": "type text",
            "clothes chrome": "close chrome",
            "close crumb": "close chrome",
            "close crome": "close chrome",
            "open crow": "open chrome",
            "open grown": "open chrome",
            "open groom": "open chrome",
            "take screen short": "take screenshot",
            "take a screen short": "take screenshot",
            "take a screen shot": "take screenshot",
            "take screenshot": "take screenshot",
            "screen shoot": "screenshot",
            "reed screen": "read screen",
            "red screen": "read screen",
            "read scream": "read screen",
            "click clink": "click link",
            "click the clink": "click the link",
            "right this": "write this",
            "wright this": "write this",
            "right me": "write me",
            "wright me": "write me",
            "coffee text": "copy text",
            "copy tax": "copy text",
            "high light": "highlight",
            "highlite": "highlight",
            "hi light": "highlight",
            "jarvis": "jarvis",
            "service": "jarvis",
            "travis": "jarvis",
            "jervis": "jarvis",
            "hey service": "hey jarvis",
            "hey travis": "hey jarvis",
            "hey jervis": "hey jarvis",
            "go sleep": "go to sleep",
            "go asleep": "go to sleep",
            "stop talking": "stop",

            "close current tap": "close current tab",
            "close recent tab": "close current tab",
            "close most reason tab": "close most recent tab",
            "closed tab": "close tab",
            "new tap": "new tab",
            "open new tap": "open new tab",
            "reopen close tab": "reopen closed tab",
            "open google dogs": "open google docs",
            "open google docks": "open google docs",
            "open goggles docs": "open google docs",
            "google dogs": "google docs",
            "google docks": "google docs",
            "create text file": "create txt file",
            "create tax file": "create txt file",
            "create txt fall": "create txt file",
            "right me an essay": "write me an essay",
            "write mean essay": "write me an essay",
            "surge for": "search for",
            "church for": "search for",
            "open the third book mark": "open the third bookmark",
            "book mark": "bookmark",
        }
        self.command_heads: List[str] = [
            "paste text", "type", "write", "write me", "open", "close", "click", "double click",
            "right click", "highlight", "select", "copy", "read screen", "take screenshot",
            "screenshot", "analyze screenshot", "google", "youtube", "go to", "search", "remember",
            "forget", "what do you remember", "create file", "create a file", "make file",
            "make a file", "read file", "read my homework", "system info", "list files", "find file",
            "scroll up", "scroll down", "press", "move mouse", "run command", "switch to",
            "minimize", "maximize", "go to sleep", "wake up", "stop", "close current tab", "close tab", "new tab", "reopen closed tab", "open bookmark", "list bookmarks", "open google docs", "autopilot", "research", "open latest notes", "where are the notes"
        ]

    def clean(self, text: str) -> str:
        text = text or ""
        text = text.strip().lower()
        text = text.replace("’", "'").replace("“", '"').replace("”", '"')
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"^(hey|okay|ok|yo|hello)\s+(jarvis|service|travis|jervis)[,\s]*", "", text).strip()
        return text

    def normalize(self, text: str) -> NormalizedCommand:
        original = text or ""
        cleaned = self.clean(original)
        fixed = cleaned
        changed = False
        reasons: List[str] = []
        for wrong, right in sorted(self.phrase_replacements.items(), key=lambda x: len(x[0]), reverse=True):
            if wrong in fixed:
                fixed = fixed.replace(wrong, right)
                changed = True
                reasons.append(f"{wrong}->{right}")
        fixed = re.sub(r"\s+", " ", fixed).strip()
        confidence = 0.98 if changed else 0.9
        if not changed:
            corrected = self._fuzzy_head_fix(fixed)
            if corrected != fixed:
                changed = True
                reasons.append("fuzzy command head")
                fixed = corrected
                confidence = 0.82
        if not fixed:
            confidence = 0.0
        return NormalizedCommand(original=original, text=fixed, confidence=confidence, changed=changed, reason=", ".join(reasons) if reasons else "none")

    def _fuzzy_head_fix(self, text: str) -> str:
        words = text.split()
        if not words:
            return text
        for n in (3, 2, 1):
            if len(words) >= n:
                head = " ".join(words[:n])
                match = difflib.get_close_matches(head, self.command_heads, n=1, cutoff=0.78)
                if match and match[0] != head:
                    return " ".join([match[0]] + words[n:]).strip()
        return text

    def likely_meant(self, text: str, options: List[str]) -> Tuple[str, float]:
        cleaned = self.clean(text)
        match = difflib.get_close_matches(cleaned, options, n=1, cutoff=0.55)
        if not match:
            return "", 0.0
        ratio = difflib.SequenceMatcher(None, cleaned, match[0]).ratio()
        return match[0], ratio
