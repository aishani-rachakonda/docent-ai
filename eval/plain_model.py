"""The README's sample queries, sent to the same model with no tools and no system prompt.

    uv run python eval/plain_model.py

Writes eval/runs/plain.json: {label: {prompt, model, reply}}.
"""
import json
import os
from pathlib import Path

import litellm
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent / ".env")
MODEL = "vertex_ai/gemini-3.5-flash"

PROMPTS = {
    "animals": "I have an hour and love animals, especially cats and horses. Plan me a tour.",
    "monet": "How many works by Claude Monet are on view, and where? Plan me a tour of them.",
    "egypt": "It's my first time at The Met and I've always been fascinated by ancient Egypt. "
             "Can you show me the highlights in about an hour?",
    "myths": "Can you plan a 45-minute tour of Greek and Roman gods and heroes?",
    "china": "I'd love to spend 90 minutes with Chinese art, especially ceramics and landscape paintings.",
}

out = {}
for label, prompt in PROMPTS.items():
    r = litellm.completion(model=MODEL, messages=[{"role": "user", "content": prompt}],
                           vertex_project=os.environ.get("GOOGLE_CLOUD_PROJECT"), vertex_location="global",
                           num_retries=4)
    out[label] = {"prompt": prompt, "model": MODEL, "reply": r.choices[0].message.content}
    print(label, len(out[label]["reply"] or ""))
(HERE / "runs" / "plain.json").write_text(json.dumps(out, indent=1))
