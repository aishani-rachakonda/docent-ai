"""Check a reply's citations in code, without a model.

Every [met:<id>] must name an object the agents actually looked up in this run, and every
[wikipedia:<title>] an article they actually read. Sentences that state something but carry no
tag are listed too. Then each cited sentence's specific details (names, places, numbers) must
appear in the sources it cites: the Met record for [met:<id>], the article text for
[wikipedia:<title>]. The writer gets these problems back and revises once.

The detail check catches a fact pinned on the wrong source (a hospital in Saint-Remy cited to a
painting's Met record, which never mentions it). It cannot judge a paraphrased claim; that is
left to the evaluation.
"""

import json
import re
import unicodedata
from functools import lru_cache

import met_tools
import wikipedia

# A tag is [met:<id>], [wikipedia:<title>] or [data]; writers sometimes combine several in one
# bracket, e.g. [met:1, wikipedia:Barding], which counts as each of its parts.
TAG = re.compile(r"\[((?:met|wikipedia):[^\]]+|data)\]")
_PART = re.compile(r"[,;]\s*(?=(?:met|wikipedia):|data\b)")


def tags(text: str) -> list[tuple[str, str]]:
    """Every (kind, ref) cited in the text: ('met', '123'), ('wikipedia', 'Barding'), ('data', '')."""
    out = []
    for group in TAG.findall(text):
        for part in _PART.split(group):
            kind, _, ref = part.partition(":")
            out.append((kind.strip(), ref.strip()))
    return out


# Text the reply may contain without a citation: headings, route notes, questions, short lines
_EXEMPT = re.compile(r"^\s*(#|\*[^*\s]|\*{0,2}before you go|[-*]\s*(walk|start|route|stop|about|note|optional|removed))", re.I)


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


# Capitalized words that start sentences or clauses but name nothing
_STOP = set("""the this these that those it its in at on of for from to by with as when while during after before
since because although though unlike like both each one many some most such instead nearby finally also today
here there his her their he she they you your we our look notice see a an and but or if so yet then than its
known called made created painted carved crafted designed built cast its it's this's these's during, ce bce ad bc
pharaoh king queen emperor empress prince princess god goddess lord lady
""".split())
_NUM = re.compile(r"(?<![\w.])\d{2,}(?:[.,]\d+)?(?![\w])")
_NAME = re.compile(r"[A-Z][\w’'\-]*[\w]", re.U)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower().replace("’", "'")


@lru_cache(maxsize=1024)
def _met_text(object_id: str) -> str:
    record = met_tools.get_object(int(object_id))
    return "" if "error" in record else _fold(json.dumps(record, default=str, ensure_ascii=False))


@lru_cache(maxsize=512)
def _wiki_text(title: str) -> str | None:
    page = wikipedia.fetch(title)
    return None if "error" in page else _fold(page["title"] + "\n" + page["text"])


# A place in the text often appears in the record as its adjective, and the other way round
_DEMONYM = {"france": "french", "egypt": "egyptian", "greece": "greek", "spain": "spanish", "germany": "german",
            "china": "chinese", "japan": "japanese", "netherlands": "dutch", "holland": "dutch", "england": "english",
            "britain": "british", "persia": "persian", "iran": "iranian", "italy": "italian", "rome": "roman",
            "crete": "cretan", "turkey": "turkish", "india": "indian", "korea": "korean", "mexico": "mexican",
            "flanders": "flemish", "assyria": "assyrian", "byzantium": "byzantine", "venice": "venetian"}
_DEMONYM.update({v: k for k, v in list(_DEMONYM.items())})


def _in(word: str, source: str) -> bool:
    """A detail is in the source if the word, its stem (Egyptians -> egyptian, Buddhism -> buddhi), its
    place/adjective pair (Italy -> italian), or for a year the short form of a range (1590 -> 1580-90) is."""
    w = _fold(word).strip("'-").removesuffix("'s")
    if not w:
        return True
    if w in source:
        return True
    if w in _DEMONYM and _DEMONYM[w] in source:
        return True
    if re.fullmatch(r"\d{4}", w) and re.search(rf"\d[-–/]{w[2:]}\b", source):
        return True
    for suffix in ("es", "s", "ians", "ian", "ism", "ist", "ists", "ic", "ese", "ish"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 4 and w[: -len(suffix)] in source:
            return True
    return False


def _details(sentence: str) -> list[str]:
    """Names, places and numbers in a sentence: the parts that must come from a source."""
    found = []
    first = re.match(r"\W*([\w’'\-]+)", sentence)
    first_word = first.group(1) if first else ""
    for m in _NAME.finditer(sentence):
        if m.start() <= sentence.find(first_word) and m.group(0) == first_word:
            continue  # the sentence's first word is capitalized anyway: "Sadly", "Scholars", "Holding"
        for part in m.group(0).split("-"):
            if part[:1].isupper() and _fold(part) not in _STOP and len(part) > 1:
                found.append(part)
    found += _NUM.findall(sentence)
    return list(dict.fromkeys(found))


def _split(line: str) -> list[str]:
    """Sentences of one line. Split after a full stop unless tags follow it, or after a sentence's
    closing tags: '... wheat. [met:1] It was ...' is two sentences, the tag going with the first."""
    parts = re.split(r"(?<=[.!?])\s+(?!\[)|(?<=\])\s+(?=[A-Z\"“])", line)
    return [p for p in parts if p and p.strip()]


def _sentences(text: str) -> list[str]:
    """Sentences with their tags: a tag after the full stop ('... France. [met:1]') stays with its sentence."""
    out = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(("#", "*", "- ")):
            continue  # headings, meta lines, and route notes (which echo the visitor's own request)
        out += _split(line)
    return out


def unsupported(reply: str) -> list[dict]:
    """Cited sentences with details that none of their cited sources contain."""
    problems = []
    for sentence in _sentences(reply):
        cited = [(k, r) for k, r in tags(sentence) if k in ("met", "wikipedia")]
        if not cited:
            continue
        texts = []
        for kind, ref in cited:
            t = _met_text(ref) if kind == "met" and ref.isdigit() else _wiki_text(ref) if kind == "wikipedia" else ""
            if t is None:  # the article cannot be fetched: nothing to check against
                texts = None
                break
            texts.append(t)
        if texts is None:
            continue
        source = "\n".join(texts)
        claim = TAG.sub(" ", sentence)
        missing = [d for d in _details(claim) if not _in(d, source)]
        if missing:
            problems.append({"sentence": claim.strip()[:220], "cited": [f"{k}:{r}" for k, r in cited],
                             "not_in_cited_sources": missing})
    return problems


def check(reply: str, tool_calls: list[dict]) -> dict:
    ids, titles = sources_seen(tool_calls)
    bad = []
    queried = any(c.get("name") in ("run_sql", "search_objects", "gallery_summary") for c in tool_calls)
    for kind, ref in tags(reply):
        if kind == "data":
            if not queried:
                bad.append("[data] is used, but no query (run_sql, search_objects, gallery_summary) ran.")
            continue
        if kind == "met" and ref not in ids:
            bad.append(f"[met:{ref}] is not an object any tool returned in this conversation turn.")
        if kind == "wikipedia" and ref.lower() not in titles:
            bad.append(f"[wikipedia:{ref}] is not an article that was read with get_wikipedia.")
    uncited = []
    for line in reply.splitlines():
        if not line.strip() or _EXEMPT.match(line) or line.strip().endswith("?"):
            continue
        for sentence in _split(line):
            words = re.findall(r"[A-Za-z]{3,}", TAG.sub(" ", sentence))
            if len(words) >= 8 and not TAG.search(sentence):
                uncited.append(sentence.strip()[:160])
    wrong_source = unsupported(reply)
    return {"ok": not bad and not uncited and not wrong_source, "unknown_sources": bad,
            "uncited_sentences": uncited, "details_not_in_cited_source": wrong_source, "tags": len(tags(reply))}
