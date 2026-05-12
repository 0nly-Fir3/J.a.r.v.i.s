
import json
from typing import Any, Dict, List


class AutopilotAgent:
    """Small bounded planner that maps broad goals to safe local commands."""
    def __init__(self, ai) -> None:
        self.ai = ai

    def plan(self, goal: str, context: str = "") -> List[str]:
        system = (
            "You create a SHORT safe command plan for a Windows voice assistant. "
            "Return JSON only, with key steps as a list of commands. "
            "Allowed commands include: open chrome, google QUERY, open google docs, create txt file called NAME with TEXT, "
            "write me TEXT, read screen, summarize page, start writing mode, paste last text. "
            "Do not include destructive actions, purchases, sending messages, or shell commands. Max 6 steps."
        )
        raw = self.ai.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": f"Goal: {goal}\nContext:\n{context[:6000]}"},
        ], max_tokens=800, temperature=0.2)
        try:
            data = json.loads(raw.strip().strip('`').replace('json\n',''))
            steps = data.get("steps", [])
            return [str(s).strip() for s in steps if str(s).strip()][:6]
        except Exception:
            return []
