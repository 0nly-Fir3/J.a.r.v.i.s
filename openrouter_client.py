import base64
import json
import os
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()


class OpenRouterClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip()
        self.vision_model = os.getenv("OPENROUTER_VISION_MODEL", self.model).strip()
        self.site_url = os.getenv("OPENROUTER_SITE_URL", "http://127.0.0.1:5050").strip()
        self.app_name = os.getenv("OPENROUTER_APP_NAME", "JARVIS V3").strip()
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    def ready(self) -> bool:
        return bool(self.api_key and self.api_key != "your_openrouter_key_here")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.app_name,
        }

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.45, max_tokens: int = 1200) -> str:
        if not self.ready():
            return "OpenRouter API key is missing. Add it to .env and restart JARVIS."
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            r = requests.post(self.base_url, headers=self._headers(), data=json.dumps(payload), timeout=60)
            if r.status_code >= 400:
                return f"OpenRouter error {r.status_code}: {r.text[:500]}"
            data = r.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "I did not get a response.")
        except Exception as e:
            return f"OpenRouter request failed: {e}"

    def vision(self, image_path: str, prompt: str, temperature: float = 0.25, max_tokens: int = 1400) -> str:
        if not self.ready():
            return "OpenRouter API key is missing. Add it to .env and restart JARVIS."
        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
            payload: Dict[str, Any] = {
                "model": self.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                        ],
                    }
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            r = requests.post(self.base_url, headers=self._headers(), data=json.dumps(payload), timeout=90)
            if r.status_code >= 400:
                return f"OpenRouter vision error {r.status_code}: {r.text[:500]}"
            data = r.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "I could not analyze the screenshot.")
        except Exception as e:
            return f"Vision request failed: {e}"
