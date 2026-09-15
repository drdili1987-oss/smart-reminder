import logging
from typing import Optional
import edge_tts

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "uz-UZ-MadinaNeural"


async def text_to_speech_bytes(text: str, voice: str = DEFAULT_VOICE) -> Optional[bytes]:
    """Convert text to speech audio bytes using Microsoft Edge TTS with Uzbek neural voice."""
    try:
        communicate = edge_tts.Communicate(text, voice)
        data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                data += chunk["data"]
        return data if data else None
    except Exception as exc:
        logger.exception("Text to speech conversion failed: %s", exc)
        return None
