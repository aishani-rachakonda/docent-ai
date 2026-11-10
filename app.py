"""Docent AI: a museum companion for The Met, served with FastAPI.

POST /chat keeps Project 1's shape: {response, session_id, tool_calls}, where each tool call
carries the agent that made it. A request may include a photo of a wall label.
"""

import asyncio
import os
import threading
import uuid
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv(Path(__file__).parent / ".env")

import guide  # noqa: E402  (reads model settings from the environment loaded above)
import met_tools  # noqa: E402

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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    with _sessions_lock:
        session_id = request.session_id if request.session_id in sessions else str(uuid.uuid4())
        sessions.setdefault(session_id, [])
        lock = locks.setdefault(session_id, asyncio.Lock())
    message: str | list = request.message
    if request.image:
        message = [{"type": "input_text", "text": request.message or "What is this? (photo of a wall label)"},
                   {"type": "input_image", "image_url": request.image, "detail": "high"}]
    async with lock:
        try:
            reply, tool_calls, history = await guide.chat(sessions[session_id], message)
            # Keep the conversation, but not the photo itself: it was read once, and is not stored
            sessions[session_id] = [_drop_images(m) for m in history]
        except Exception as e:  # auth, quota, a model that won't stop: show it in the chat, not as a 500
            reply, tool_calls = f"Something went wrong: {type(e).__name__}: {str(e)[:300]}", []
    return ChatResponse(response=reply, session_id=session_id, tool_calls=tool_calls)


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
