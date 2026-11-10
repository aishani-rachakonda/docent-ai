"""Send one message to the guide in-process and print the reply and tool calls.

    uv run scripts/try_chat.py "What is 1993.l32? The label says Wheat Field with Cypresses."
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
import guide  # noqa: E402


async def main(messages: list[str]) -> None:
    history: list = []
    for message in messages:
        start = time.time()
        reply, calls, history = await guide.chat(history, message)
        print(f"\n>>> {message}\n--- {time.time() - start:.0f} s, {len(calls)} tool calls")
        for c in calls:
            print(f"  [{c['agent']}] {c['name']}({json.dumps(c['args'], ensure_ascii=False)[:160]})")
            if c["name"] in ("research", "plan_route"):
                print("      -> " + c["result"][:1500].replace("\n", " "))
        print("--- reply:\n" + reply)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
