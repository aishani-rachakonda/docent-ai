"""Check a reply's citations in code, without a model.

Every [met:<id>] must name an object the agents actually looked up in this run, and every
[wikipedia:<title>] an article they actually read. Sentences that state something but carry no
tag are listed too. The Writer gets these problems back and revises once.
"""

import json
import re

TAG = re.compile(r"\[(met|wikipedia):\s*([^\]]+)\]|\[(data)\]")
# Text the reply may contain without a citation: headings, route notes, questions, short lines
_EXEMPT = re.compile(r"^\s*(#|\*{0,2}before you go|[-*]\s*(walk|start|route|stop|about|note|optional|removed))", re.I)


def sources_seen(tool_calls: list[dict]) -> tuple[set[str], set[str]]:
    """Object IDs and Wikipedia titles that appeared in this run's tool results."""
    ids, titles = set(), set()
    for call in tool_calls:
        text = call.get("result", "")
        ids.update(re.findall(r'"object_id":\s*(\d+)', text))
        if call.get("name") == "run_sql":  # rows come back as lists: take the object_id column
            try:
                data = json.loads(text)
                col = data["columns"].index("object_id")
                ids.update(str(row[col]) for row in data["rows"])
            except (ValueError, KeyError, TypeError, IndexError):
                pass
        if call.get("name") == "get_wikipedia":
            m = re.search(r'"title":\s*"([^"]+)"', text)
            if m and '"error"' not in text:
                titles.add(m.group(1).lower())
                # a redirect returns the canonical title; the title that was asked for counts too
                asked = (call.get("args") or {}).get("title")
                if asked:
                    titles.add(str(asked).lower())
    return ids, titles


def check(reply: str, tool_calls: list[dict]) -> dict:
    ids, titles = sources_seen(tool_calls)
    bad = []
    queried = any(c.get("name") in ("run_sql", "search_objects", "gallery_summary") for c in tool_calls)
    for kind, ref, data in TAG.findall(reply):
        if data:
            if not queried:
                bad.append("[data] is used, but no query (run_sql, search_objects, gallery_summary) ran.")
            continue
        ref = ref.strip()
        if kind == "met" and ref not in ids:
            bad.append(f"[met:{ref}] is not an object any tool returned in this conversation turn.")
        if kind == "wikipedia" and ref.lower() not in titles:
            bad.append(f"[wikipedia:{ref}] is not an article that was read with get_wikipedia.")
    uncited = []
    for line in reply.splitlines():
        if not line.strip() or _EXEMPT.match(line) or line.strip().endswith("?"):
            continue
        for sentence in re.split(r"(?<=[.!])\s+", line):
            words = re.findall(r"[A-Za-z]{3,}", sentence)
            if len(words) >= 8 and not TAG.search(sentence):
                uncited.append(sentence.strip()[:160])
    return {"ok": not bad and not uncited, "unknown_sources": bad, "uncited_sentences": uncited,
            "tags": len(TAG.findall(reply))}
