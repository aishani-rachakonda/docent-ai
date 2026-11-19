"""Run one prompt through the agent and save everything needed to compare versions.

    uv run python eval/run_prompt.py baseline
    uv run python eval/run_prompt.py faster

Writes eval/runs/<label>.json: the prompt, the full reply, every live step with its time, every
tool call, and summary timings (total, first story ready, per-agent counts).
"""
import asyncio
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
import guide  # noqa: E402

PROMPT = "I have an hour and love animals, especially cats and horses. Plan me a tour."


async def main(label: str) -> None:
    events: asyncio.Queue = asyncio.Queue()
    seen: list[dict] = []
    started = time.monotonic()

    async def drain():
        while True:
            e = await events.get()
            seen.append({k: v for k, v in e.items() if k != "result"} | (
                {"result": e["result"][:600]} if "result" in e else {}))

    task = asyncio.create_task(drain())
    reply, calls, _ = await guide.chat([], PROMPT, events=events)
    total = round(time.monotonic() - started, 1)
    await asyncio.sleep(0.2)
    task.cancel()

    names = list(dict.fromkeys(e["agent"] for e in seen if e["type"] == "agent"))  # each agent once, as the page counts them
    agents = Counter(n.split(" ")[0] for n in names)
    stories = [e["t"] for e in seen if e["type"] == "agent_end" and e["agent"].startswith("Storyteller")]
    stop_events = [e["t"] for e in seen if e["type"] == "stop"]
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = ""
    out = {
        "label": label,
        "prompt": PROMPT,
        "commit": commit,
        "settings": {
            "lead_effort": guide.SETTINGS.extra_args.get("reasoning_effort"),
            "story_effort": getattr(guide, "STORY_SETTINGS", guide.SETTINGS).extra_args.get("reasoning_effort"),
            "models": {k: getattr(guide, k).model for k in ("LEAD_MODEL", "RESEARCH_MODEL", "STORY_MODEL", "WRITER_MODEL") if hasattr(guide, k)},
            "story_cap_s": getattr(guide, "STORY_TIMEOUT", None),
        },
        "timing": {
            "total_s": total,
            "first_story_s": min(stories) if stories else None,
            "last_story_s": max(stories) if stories else None,
            "first_stop_shown_s": min(stop_events) if stop_events else None,
        },
        "counts": {"agents": sum(agents.values()), "by_agent": dict(agents), "tool_calls": len(calls)},
        "reply": reply,
        "tool_calls": calls,
        "events": seen,
    }
    path = ROOT / "eval" / "runs" / f"{label}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({"saved": str(path), **out["timing"], **out["counts"]}, indent=1))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "run"))
