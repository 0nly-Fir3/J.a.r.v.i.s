import asyncio
import os
import time
from pathlib import Path
from typing import Optional


class TTSEngine:
    def __init__(self) -> None:
        self.voice = os.getenv("EDGE_TTS_VOICE", "en-US-GuyNeural")
        self.out_dir = Path("data/tts")
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except Exception:
            return False

    def create_audio(self, text: str) -> Optional[str]:
        try:
            import edge_tts
        except Exception:
            return None

        safe_text = (text or "").strip()
        if not safe_text:
            return None

        filename = self.out_dir / f"reply_{int(time.time() * 1000)}.mp3"

        async def run() -> None:
            communicate = edge_tts.Communicate(safe_text, self.voice)
            await communicate.save(str(filename))

        try:
            asyncio.run(run())
            return str(filename.resolve())
        except RuntimeError:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(run())
                loop.close()
                return str(filename.resolve())
            except Exception:
                return None
        except Exception:
            return None
