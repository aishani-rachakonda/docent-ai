"""Fetch plain-text English Wikipedia articles (the public MediaWiki API, no account needed).

Wikimedia rejects requests whose User-Agent has no contact URL or email, so set WIKI_CONTACT
(e.g. the project's GitHub URL). Articles are cached in memory for the life of the process.
"""

import os
from functools import lru_cache

import httpx

API = "https://en.wikipedia.org/w/api.php"
MAX_CHARS = 6_000  # the intro and first sections: enough for a tour stop, small enough for context


def _headers() -> dict:
    return {"User-Agent": f"met-guide/0.1 ({os.environ.get('WIKI_CONTACT', '')}; student course project)"}


@lru_cache(maxsize=512)
def fetch(title: str) -> dict:
    """Return {title, url, text} for an English Wikipedia article, or {error}."""
    if not os.environ.get("WIKI_CONTACT"):
        return {"error": "Wikipedia is not configured (WIKI_CONTACT is unset)."}
    params = {"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
              "titles": title, "format": "json", "formatversion": 2}
    try:
        r = httpx.get(API, params=params, headers=_headers(), timeout=20)
        r.raise_for_status()
    except httpx.HTTPError as e:
        return {"error": f"Could not fetch '{title}': {type(e).__name__}"}
    page = r.json()["query"]["pages"][0]
    if page.get("missing") or not page.get("extract"):
        return {"error": f"No English Wikipedia article titled '{title}'."}
    text = page["extract"]
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n[Article truncated.]"
    return {"title": page["title"], "url": "https://en.wikipedia.org/wiki/" + page["title"].replace(" ", "_"), "text": text}
