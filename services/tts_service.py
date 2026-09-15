import logging
from typing import Optional
import edge_tts

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "uz-UZ-SardorNeural"


async def text_to_speech_bytes(
    text: str,
    voice: str = DEFAULT_VOICE,
    pitch: str = "-10Hz",
    rate: str = "-3%",
) -> Optional[bytes]:
    """Convert text to speech audio bytes using Microsoft Edge TTS with Uzbek male neural voice."""
    try:
        communicate = edge_tts.Communicate(text, voice, pitch=pitch, rate=rate)
        data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                data += chunk["data"]
        return data if data else None
    except Exception as exc:
        logger.exception("Text to speech conversion failed: %s", exc)
        return None
