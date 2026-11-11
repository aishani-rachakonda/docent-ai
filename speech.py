"""Read text aloud with a natural voice: Gemini's text-to-speech model on Vertex AI.

The page sends one paragraph at a time (a stop's title and "Look for", then its story) and fetches
the next while the current one plays, so no sentence is ever left between two requests. Audio comes back as 24 kHz mono PCM, wrapped here in a
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
MAX_CHARS = 5000  # a whole paragraph per request: a story is about 1,500 characters

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
    async with _gate, httpx.AsyncClient(timeout=180) as client:
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


# --- Streaming: a paragraph's audio plays while it is still being made ---
# POST /speak/start begins making the audio and returns an id; GET /speak/audio/<id> streams it as
# MP3 while the voice model sends it (the first sound arrives in about a second). Starting early is
# also how the page prepares the next paragraph while the current one plays. Finished audio stays
# in memory, so replaying costs nothing.

import hashlib
import json

import lameenc


class _Job:
    def __init__(self):
        self.chunks: list[bytes] = []
        self.done = False
        self.error: str | None = None
        self.seconds = 0.0  # length of the audio made so far; the whole length once done
        self.chars = 0
        self.changed = asyncio.Condition()

    @property
    def short(self) -> bool:
        """The voice model sometimes stops before the end of a long paragraph. Speech runs about 14
        characters a second; finished audio much shorter than that means the end is missing."""
        return self.done and self.seconds > 0 and self.chars / self.seconds > 19

    async def add(self, data: bytes) -> None:
        async with self.changed:
            if data:
                self.chunks.append(data)
            self.changed.notify_all()


_jobs: OrderedDict[str, _Job] = OrderedDict()
_JOBS = 200


def start(text: str, voice: str = VOICE, fresh: bool = False) -> str:
    """Begin making the audio for this text (unless it is made or being made); return its id. With
    fresh, make it again even if it was made before: a retry after the voice stopped early."""
    text = text.strip()[:MAX_CHARS]
    key = hashlib.sha1(f"{MODEL}|{voice}|{text}".encode()).hexdigest()[:24]
    job = _jobs.get(key)
    if job is None or (job.done and (job.error or (fresh and job.short))):
        job = _jobs[key] = _Job()
        job.chars = len(text)
        asyncio.create_task(_produce(job, text, voice))
        while len(_jobs) > _JOBS:
            old_key, old = next(iter(_jobs.items()))
            if not old.done:
                break
            _jobs.pop(old_key)
    _jobs.move_to_end(key)
    return key


async def _produce(job: _Job, text: str, voice: str) -> None:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    url = (f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/"
           f"publishers/google/models/{MODEL}:streamGenerateContent?alt=sse")
    body = {"contents": [{"role": "user", "parts": [{"text": STYLE + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    encoder = None
    try:
        async with _gate, httpx.AsyncClient(timeout=180) as client:
            for attempt in range(RETRIES):
                async with client.stream("POST", url, json=body,
                                         headers={"Authorization": f"Bearer {await _token()}"}) as r:
                    if r.status_code in (429, 500, 503) and attempt < RETRIES - 1:
                        await r.aread()
                        await asyncio.sleep(1.5 * 2 ** attempt)
                        continue
                    if r.status_code != 200:
                        await r.aread()
                        r.raise_for_status()
                    async for line in r.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        for part in json.loads(line[6:]).get("candidates", [{}])[0].get("content", {}).get("parts", []):
                            data = part.get("inlineData")
                            if not data:
                                continue
                            if encoder is None:
                                rate = int((re.search(r"rate=(\d+)", data.get("mimeType", "")) or [0, 24000])[1])
                                encoder = lameenc.Encoder()
                                encoder.set_bit_rate(64)
                                encoder.set_in_sample_rate(rate)
                                encoder.set_channels(1)
                                encoder.set_quality(2)
                            pcm = base64.b64decode(data["data"])
                            job.seconds += len(pcm) / 2 / rate
                            await job.add(bytes(encoder.encode(pcm)))
                    break
        if encoder is not None:
            await job.add(bytes(encoder.flush()))
        elif not job.chunks:
            job.error = "no audio"
    except Exception as e:  # the page falls back to the browser's own voice for this paragraph
        job.error = f"{type(e).__name__}"
    finally:
        job.done = True
        await job.add(b"")


def status(key: str) -> _Job | None:
    return _jobs.get(key)


async def stream(job: _Job):
    """The job's MP3 bytes: what is made so far, then the rest as it arrives."""
    sent = 0
    while True:
        async with job.changed:
            await job.changed.wait_for(lambda: len(job.chunks) > sent or job.done)
            ready = job.chunks[sent:]
            finished = job.done
        for chunk in ready:
            yield chunk
        sent += len(ready)
        if finished and sent >= len(job.chunks):
            return
