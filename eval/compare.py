"""Compare two saved runs of the same prompt (see run_prompt.py), for people and for an LLM judge.

    uv run python eval/compare.py baseline faster

Writes:
  eval/judge_pack.md      both tours, blind (Tour A / Tour B), with a rubric and a JSON answer format
  eval/judge_key.json     which label is A and which is B (keep it away from the judge)
The notebook eval/compare.ipynb uses the same functions to show timings and the tours side by side.
"""
import json
import random
import re
import sys
from pathlib import Path

RUNS = Path(__file__).resolve().parent / "runs"
STOP = re.compile(r"^### (\S+?)\. (.+?) — Gallery (.+)$", re.M)


def load(label: str) -> dict:
    return json.loads((RUNS / f"{label}.json").read_text())


def stops(reply: str) -> list[dict]:
    """Each stop in a tour: number, title, gallery, its story's length and sources."""
    heads = list(STOP.finditer(reply))
    out = []
    for k, m in enumerate(heads):
        end = heads[k + 1].start() if k + 1 < len(heads) else len(reply)
        text = reply[m.end():end]
        text = re.split(r"^## ", text, flags=re.M)[0]  # stop at the next section heading
        story = re.sub(r"^\*.*\*.*$", "", text, count=1, flags=re.M)
        look = re.search(r"^Look for: (.+)$", story, re.M)
        body = story[:look.start()] if look else story
        words = len(re.sub(r"\[[^\]]+\]", "", body).split())
        out.append({
            "n": m.group(1), "title": m.group(2).strip(), "gallery": m.group(3).strip(),
            "words": words,
            "met_cites": len(re.findall(r"\[met:", body)),
            "wikipedia_cites": len(set(re.findall(r"\[wikipedia:([^\]]+)\]", body))),
            "look_for": bool(look),
            "fallback": "The Met's record has the details" in body,
        })
    return out


def summary(run: dict) -> dict:
    st = stops(run["reply"])
    t = run["timing"]
    return {
        "version": run["label"],
        "total (s)": t["total_s"],
        "first stop on screen (s)": t.get("first_stop_shown_s") or t["total_s"],
        "last story done (s)": t.get("last_story_s"),
        "agents": run["counts"]["agents"],
        "tool calls": run["counts"]["tool_calls"],
        "stops": len(st),
        "avg story words": round(sum(s["words"] for s in st) / len(st)) if st else 0,
        "Wikipedia articles cited": sum(s["wikipedia_cites"] for s in st),
        "stops with Look for": sum(s["look_for"] for s in st),
        "stopped at time limit": sum(1 for e in run["events"] if e["type"] == "limit"),
    }


def stages(run: dict) -> list[dict]:
    """When each agent started and finished, in seconds into the turn."""
    spans: dict[str, dict] = {}
    for e in run["events"]:
        if e["type"] == "agent":
            spans.setdefault(e["agent"], {"agent": e["agent"], "start": e["t"], "end": None})
        elif e["type"] == "agent_end" and e["agent"] in spans:
            spans[e["agent"]]["end"] = e["t"]
    return list(spans.values())


RUBRIC = """\
You are judging two versions of a museum-guide AI. Both got the same request from a visitor to
The Met. Judge only what is on the page; you do not need to check facts against outside sources,
but do flag anything that reads as made up, wrong, or unsupported by its citation tags.

Score each tour from 1 (poor) to 5 (excellent) on:
1. relevance: do the stops fit the request (the interests and the time given)?
2. explanation: would a curious non-expert understand what each object is and why it matters?
   Are unfamiliar names and terms explained?
3. grounding: does every fact carry a source tag ([met:…], [wikipedia:…], [data])? Any claims that
   look unsupported?
4. look_for: are the "Look for" lines concrete and useful in front of the object?
5. writing: warm, clear, and pleasant to hear read aloud; no hype words or filler.
6. completeness: does every stop have a real story (not a stub)? Is the route usable?

Then say which tour is better overall, or "tie", and whether the difference is small, clear or large.

Answer with JSON only:
{"A": {"relevance": n, "explanation": n, "grounding": n, "look_for": n, "writing": n, "completeness": n},
 "B": {...same keys...},
 "better": "A" | "B" | "tie",
 "difference": "none" | "small" | "clear" | "large",
 "reasons": "three or four sentences",
 "weakest_stops": {"A": ["stop numbers"], "B": ["stop numbers"]}}
"""


def judge_pack(a_label: str, b_label: str, seed: int | None = None, swap: bool | None = None) -> tuple[str, dict]:
    runs = [load(a_label), load(b_label)]
    if swap is None:
        random.Random(seed).shuffle(runs)  # blind: the judge doesn't know which version is which
    elif swap:
        runs.reverse()
    key = {"A": runs[0]["label"], "B": runs[1]["label"]}
    text = (f"{RUBRIC}\n## The visitor's request\n\n{runs[0]['prompt']}\n\n"
            f"## Tour A\n\n{runs[0]['reply']}\n\n## Tour B\n\n{runs[1]['reply']}\n")
    return text, key


def judge(a_label: str, b_label: str, model: str = "vertex_ai/gemini-3.1-pro-preview") -> list[dict]:
    """Ask an LLM judge twice, with the tours in both orders (judges tend to favor one position),
    and unblind each verdict. Uses the same Vertex AI project as the app."""
    import os
    import litellm
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    verdicts = []
    for swap in (False, True):
        text, key = judge_pack(a_label, b_label, swap=swap)
        r = litellm.completion(model=model, messages=[{"role": "user", "content": text}],
                               vertex_project=os.environ.get("GOOGLE_CLOUD_PROJECT"), vertex_location="global",
                               reasoning_effort="high", num_retries=4)
        raw = r.choices[0].message.content or ""
        m = re.search(r"\{.*\}", raw, re.S)
        v = json.loads(m.group(0)) if m else {"raw": raw}
        # Unblind: name the versions
        named = {key[k]: v.get(k) for k in ("A", "B")}
        better = key.get(v.get("better"), v.get("better"))
        weakest = {key[k]: (v.get("weakest_stops") or {}).get(k) for k in ("A", "B")}
        verdicts.append({"order": f"A={key['A']}, B={key['B']}", "scores": named, "better": better,
                         "difference": v.get("difference"), "reasons": v.get("reasons"), "weakest_stops": weakest})
    return verdicts


if __name__ == "__main__":
    a, b = (sys.argv[1:3] + ["baseline", "faster"])[:2] if len(sys.argv) < 3 else sys.argv[1:3]
    text, key = judge_pack(a, b)
    here = Path(__file__).resolve().parent
    (here / "judge_pack.md").write_text(text)
    (here / "judge_key.json").write_text(json.dumps(key, indent=1))
    for label in (a, b):
        print(json.dumps(summary(load(label))))
    print("Wrote eval/judge_pack.md and eval/judge_key.json")
