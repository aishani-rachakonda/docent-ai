"""Read text aloud with a natural voice: Gemini's text-to-speech model on Vertex AI.

The page sends one or two sentences at a time and fetches the next while the current one plays,
so a stop starts speaking within seconds. Audio comes back as 24 kHz mono PCM, wrapped here in a
WAV header. Results are cached in memory, so replaying a stop costs nothing.
"""

import asyncio
import base64
import io
import os
import re
import wave
from collections import OrderedDict

import google.auth
import google.auth.transport.requests
import httpx

MODEL = os.environ.get("TTS_MODEL", "gemini-3.1-flash-tts-preview")
VOICE = os.environ.get("TTS_VOICE", "Charon")
STYLE = "Read this as a warm, unhurried museum docent speaking to one curious visitor, with natural pauses:\n\n"
MAX_CHARS = 1200

_creds = None
_creds_lock = asyncio.Lock()
_cache: OrderedDict[tuple[str, str], bytes] = OrderedDict()
_CACHE_SIZE = 300
# The voice model has a low per-minute quota: send a few requests at a time, and wait and retry
# when it says "too many requests" instead of failing (a failed piece used to be skipped).
_gate = asyncio.Semaphore(int(os.environ.get("TTS_CONCURRENCY", "2")))
RETRIES = 4


async def _token() -> str:
    global _creds
    async with _creds_lock:
        if _creds is None:
            _creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if not _creds.valid:
            await asyncio.to_thread(_creds.refresh, google.auth.transport.requests.Request())
        return _creds.token


async def synthesize(text: str, voice: str = VOICE) -> bytes:
    """Return WAV bytes for the text. Raises on failure; the page then falls back to the browser's voice."""
    text = text.strip()[:MAX_CHARS]
    key = (voice, text)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    url = (f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/"
           f"publishers/google/models/{MODEL}:generateContent")
    body = {"contents": [{"role": "user", "parts": [{"text": STYLE + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    async with _gate, httpx.AsyncClient(timeout=60) as client:
        for attempt in range(RETRIES):
            r = await client.post(url, json=body, headers={"Authorization": f"Bearer {await _token()}"})
            if r.status_code not in (429, 500, 503) or attempt == RETRIES - 1:
                break
            await asyncio.sleep(1.5 * 2 ** attempt)  # 1.5, 3, 6 s
    r.raise_for_status()
    part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
    pcm = base64.b64decode(part["data"])
    rate = int((re.search(r"rate=(\d+)", part.get("mimeType", "")) or [0, 24000])[1])
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    audio = buf.getvalue()
    _cache[key] = audio
    if len(_cache) > _CACHE_SIZE:
        _cache.popitem(last=False)
    return audio
