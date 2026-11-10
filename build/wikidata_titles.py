"""Offline build, step 3: find the English Wikipedia article for each object and artist.

The Met links objects and artists to Wikidata. Wikidata's API looks up 50 IDs per request and says
which English Wikipedia article (if any) each one has. Results go to data/raw/wikidata.jsonl
(resumable), then into a `wiki` table: qid -> enwiki title, plus the item's English label and
description, which are useful context even when there is no article.

    uv run build/wikidata_titles.py
"""

import json
import os
import time
from pathlib import Path

import duckdb
import httpx

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "met.duckdb"
OUT = ROOT / "data" / "raw" / "wikidata.jsonl"
API = "https://www.wikidata.org/w/api.php"
# Wikimedia rejects (403) clients whose User-Agent has no contact URL or email.
# Set WIKI_CONTACT to the project's repository URL.
HEADERS = {"User-Agent": f"met-guide/0.1 ({os.environ.get('WIKI_CONTACT', '')}; student course project)"}
BATCH = 50


def main() -> None:
    if not os.environ.get("WIKI_CONTACT"):
        raise SystemExit("Set WIKI_CONTACT to a contact URL (e.g. the GitHub repo); Wikimedia requires one.")
    con = duckdb.connect(str(DB))
    qids = [r[0] for r in con.execute("""
        SELECT DISTINCT qid FROM (SELECT object_qid AS qid FROM objects UNION ALL SELECT artist_qid FROM objects)
        WHERE qid IS NOT NULL ORDER BY qid""").fetchall()]
    done = set()
    if OUT.exists():
        done = {json.loads(l)["qid"] for l in OUT.open() if l.strip()}
    todo = [q for q in qids if q not in done]
    print(f"{len(qids):,} Wikidata IDs, {len(todo):,} to look up", flush=True)

    with httpx.Client(headers=HEADERS, timeout=60) as client, OUT.open("a") as out:
        for i in range(0, len(todo), BATCH):
            batch = todo[i : i + BATCH]
            params = {"action": "wbgetentities", "ids": "|".join(batch), "props": "sitelinks|labels|descriptions",
                      "sitefilter": "enwiki", "languages": "en", "format": "json", "maxlag": 5}
            for attempt in range(5):
                r = client.get(API, params=params)
                if r.status_code == 200 and "error" not in r.json():
                    break
                print(f"batch {i}: HTTP {r.status_code} {r.text[:120]}, retrying", flush=True)
                time.sleep(10 * (attempt + 1))
            else:
                raise SystemExit("Wikidata kept failing; rerun later to resume")
            entities = r.json().get("entities", {})
            for qid in batch:
                e = entities.get(qid, {})
                out.write(json.dumps({
                    "qid": qid,
                    "enwiki_title": e.get("sitelinks", {}).get("enwiki", {}).get("title"),
                    "label": e.get("labels", {}).get("en", {}).get("value"),
                    "description": e.get("descriptions", {}).get("en", {}).get("value"),
                }) + "\n")
            out.flush()
            if (i // BATCH) % 50 == 0:
                print(f"{i + len(batch):,}/{len(todo):,}", flush=True)
            time.sleep(0.5)

    con.execute(f"CREATE OR REPLACE TABLE wiki AS SELECT * FROM read_json('{OUT}', format='newline_delimited')")
    print(con.sql("""
        SELECT
          (SELECT count(*) FROM objects) AS on_view,
          (SELECT count(*) FROM objects o JOIN wiki w ON w.qid = o.object_qid WHERE w.enwiki_title IS NOT NULL) AS object_has_article,
          (SELECT count(*) FROM objects o JOIN wiki w ON w.qid = o.artist_qid WHERE w.enwiki_title IS NOT NULL) AS artist_has_article,
          (SELECT count(*) FROM objects o
             LEFT JOIN wiki a ON a.qid = o.object_qid LEFT JOIN wiki b ON b.qid = o.artist_qid
             WHERE a.enwiki_title IS NOT NULL OR b.enwiki_title IS NOT NULL) AS either_has_article
    """))
    con.close()


if __name__ == "__main__":
    main()
