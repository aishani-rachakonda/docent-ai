"""Docent AI: a museum companion for The Met, served with FastAPI.

POST /chat keeps Project 1's shape: {response, session_id, tool_calls}, where each tool call
carries the agent that made it. A request may include a photo of a wall label.

POST /chat/stream runs the same turn but sends each step as it happens (server-sent events): an
agent starting, its thinking, each tool call with the agent's reason for it, each result. The last
event, "done", carries the same {response, session_id, tool_calls} as /chat.
"""

import asyncio
import json
import os
import threading
import uuid
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

load_dotenv(Path(__file__).parent / ".env")

import guide  # noqa: E402  (reads model settings from the environment loaded above)
import met_tools  # noqa: E402
import speech  # noqa: E402

HERE = Path(__file__).parent
app = FastAPI(title="Docent AI")

# session_id -> conversation history. In memory, single process.
sessions: dict[str, list] = {}
locks: dict[str, asyncio.Lock] = {}
_sessions_lock = threading.Lock()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    # Optional photo of a wall label, as a data URL ('data:image/jpeg;base64,...')
    image: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tool_calls: list[dict]


@app.get("/")
def index():
    return FileResponse(HERE / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/snapshot")
def snapshot():
    return met_tools.snapshot_info()


@app.get("/featured")
def featured(response: Response, n: int = 12):
    """A random handful of Met highlights on view at Fifth Avenue with open-access pictures, for the landing page.
    A new draw every time: never cached."""
    response.headers["Cache-Control"] = "no-store"
    return met_tools._rows("""
        SELECT object_id, COALESCE(title, concat_ws(', ', object_name, culture)) AS title, gallery, image_small_url, met_url,
               COALESCE(NULLIF(artist, ''), culture) AS maker, object_date
        FROM objects
        WHERE is_highlight AND image_small_url IS NOT NULL AND department <> 'The Cloisters'
        ORDER BY random() LIMIT ?""", [max(1, min(n, 48))])


@app.get("/objects")
async def objects(ids: str):
    """Title, gallery, picture and Met page for a few objects, so an answer can show what it talks about.
    Some pictures are missing from the snapshot; for those, ask the Met API, as the tour's live check does."""
    out = []
    for oid in [int(i) for i in ids.split(",") if i.strip().isdigit()][:12]:
        o = met_tools.get_object(oid)
        if "error" not in o:
            out.append({**{k: o.get(k) for k in ("object_id", "artist", "object_date", "gallery", "image_small_url", "met_url")},
                        "title": guide._title(o)})
    gaps = [o["object_id"] for o in out if not o["image_small_url"]]
    if gaps:
        live = await guide._verify_live(gaps)
        for o in out:
            v = live.get(o["object_id"])
            if v and v.get("image_small_url") and not o["image_small_url"]:
                o["image_small_url"] = v["image_small_url"]
    return out


class SpeakRequest(BaseModel):
    text: str
    fresh: bool = False  # make it again: a retry after the voice stopped early


@app.post("/speak")
async def speak(request: SpeakRequest):
    """A sentence or two of a story, read aloud by a natural voice (WAV)."""
    if not request.text.strip():
        raise HTTPException(400, "No text")
    try:
        audio = await speech.synthesize(request.text)
    except Exception as e:  # the page falls back to the browser's own voice
        raise HTTPException(502, f"Speech failed: {type(e).__name__}")
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "private, max-age=86400"})


def _session(request: ChatRequest) -> tuple[str, asyncio.Lock, str | list]:
    with _sessions_lock:
        session_id = request.session_id if request.session_id in sessions else str(uuid.uuid4())
        sessions.setdefault(session_id, [])
        lock = locks.setdefault(session_id, asyncio.Lock())
    message: str | list = request.message
    if request.image:
        message = [{"type": "input_text", "text": request.message or "What is this? (photo of a wall label)"},
                   {"type": "input_image", "image_url": request.image, "detail": "high"}]
    return session_id, lock, message


async def _turn(session_id: str, lock: asyncio.Lock, message: str | list,
                events: asyncio.Queue | None = None) -> ChatResponse:
    async with lock:
        try:
            reply, tool_calls, history = await guide.chat(sessions[session_id], message, events)
            # Keep the conversation, but not the photo itself: it was read once, and is not stored
            sessions[session_id] = [_drop_images(m) for m in history]
        except Exception as e:  # auth, quota, a model that won't stop: show it in the chat, not as a 500
            if guide._busy(e):
                reply = ("Google's AI service is very busy right now, and it kept asking me to slow down even after "
                         "several retries. Please try again in a minute or two.")
            else:
                reply = f"Something went wrong: {type(e).__name__}: {str(e)[:300]}"
            tool_calls = []
    return ChatResponse(response=reply, session_id=session_id, tool_calls=tool_calls)


@app.post("/speak/start")
async def speak_start(request: SpeakRequest):
    """Begin making a paragraph's audio; returns the id to stream it from (/speak/audio/<id>)."""
    if not request.text.strip():
        raise HTTPException(400, "No text")
    return {"id": speech.start(request.text, fresh=request.fresh)}


@app.get("/speak/audio/{key}")
async def speak_audio(key: str):
    """The paragraph's audio as MP3, streamed while it is being made."""
    job = speech.status(key)
    if job is None:
        raise HTTPException(404, "Unknown audio")
    if job.done and job.error and not job.chunks:
        raise HTTPException(502, f"Speech failed: {job.error}")
    return StreamingResponse(speech.stream(job), media_type="audio/mpeg",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/speak/info/{key}")
async def speak_info(key: str):
    """Whether a paragraph's audio is finished, and its length in seconds (exact once done)."""
    job = speech.status(key)
    if job is None:
        raise HTTPException(404, "Unknown audio")
    return {"done": job.done, "seconds": round(job.seconds, 2), "short": job.short, "error": job.error}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return await _turn(*_session(request))


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """The same turn as /chat, with every step sent live as a server-sent event."""
    session_id, lock, message = _session(request)
    events: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(_turn(session_id, lock, message, events))

    def sse(event: dict) -> str:
        return f"data: {json.dumps(event, default=str, ensure_ascii=False)}\n\n"

    async def stream():
        yield sse({"type": "start", "session_id": session_id})
        while True:
            getter = asyncio.ensure_future(events.get())
            done, _ = await asyncio.wait({getter, task}, timeout=15, return_when=asyncio.FIRST_COMPLETED)
            if getter in done:
                yield sse(getter.result())
                continue
            getter.cancel()
            if task.done():
                while not events.empty():
                    yield sse(events.get_nowait())
                yield sse({"type": "done", **task.result().model_dump()})
                return
            yield ": still working\n\n"  # keeps the connection open through proxies

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _drop_images(message: dict) -> dict:
    """Replace a user's label photo with a note. Leaves every other message untouched."""
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list) or not any(isinstance(c, dict) and c.get("type") == "input_image" for c in content):
        return message
    kept = [c for c in content if not (isinstance(c, dict) and c.get("type") == "input_image")]
    return {**message, "content": kept + [{"type": "input_text", "text": "[label photo, not kept]"}]}


if __name__ == "__main__":
    # Cloud Run sets PORT and needs 0.0.0.0; locally it defaults to http://127.0.0.1:8010
    port = int(os.environ.get("PORT", 8010))
    uvicorn.run(app, host="0.0.0.0" if "PORT" in os.environ else "127.0.0.1", port=port)
