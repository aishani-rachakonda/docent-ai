"""Offline build, step 2: fetch image links for every on-view object from the Met API.

The Open Access CSV has no image links, so this asks the API for each object, slowly (about two
requests a second), to stay well clear of the Met's bot blocking. It appends one JSON line per
object to data/raw/images.jsonl, so it can stop and resume at any time; merge_images.py copies the
results into the database. Only the image links, gallery and on-view status are kept.

    uv run build/fetch_images.py            # all objects not fetched yet
    uv run build/fetch_images.py --limit 50 # a quick test
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import httpx

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "met.duckdb"
OUT = ROOT / "data" / "raw" / "images.jsonl"
API = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"
HEADERS = {"User-Agent": "met-guide/0.1 (student course project; educational, non-commercial)"}
DELAY = 0.5  # seconds between requests: ~2 a second, far under the documented 80
BACKOFF = [60, 300, 900, 1800]  # waits after a block (403/429), in seconds


def done_ids() -> set[int]:
    if not OUT.exists():
        return set()
    ids = set()
    with OUT.open() as f:
        for line in f:
            try:
                ids.add(json.loads(line)["object_id"])
            except (json.JSONDecodeError, KeyError):
                pass  # a line cut off when the script was stopped
    return ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    # Highlights first, so the most-used objects have images even if the run is cut short
    ids = [r[0] for r in con.execute(
        "SELECT object_id FROM objects ORDER BY is_highlight DESC, is_public_domain DESC, object_id").fetchall()]
    con.close()
    skip = done_ids()
    todo = [i for i in ids if i not in skip][: args.limit]
    print(f"{len(skip):,} already fetched, {len(todo):,} to go (~{len(todo) * DELAY / 3600:.1f} h)", flush=True)

    blocks = 0
    with httpx.Client(headers=HEADERS, timeout=30) as client, OUT.open("a") as out:
        for n, object_id in enumerate(todo, 1):
            while True:
                try:
                    r = client.get(API.format(object_id))
                except httpx.HTTPError as e:
                    print(f"{object_id}: {type(e).__name__}, retrying in 30 s", flush=True)
                    time.sleep(30)
                    continue
                if r.status_code in (403, 429):
                    wait = BACKOFF[min(blocks, len(BACKOFF) - 1)]
                    blocks += 1
                    print(f"{object_id}: HTTP {r.status_code} (blocked), waiting {wait} s", flush=True)
                    time.sleep(wait)
                    continue
                blocks = 0
                break
            row = {"object_id": object_id, "status": r.status_code,
                   "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            if r.status_code == 200:
                d = r.json()
                row.update(image_url=d.get("primaryImage") or None,
                           image_small_url=d.get("primaryImageSmall") or None,
                           gallery=d.get("GalleryNumber") or None)
            out.write(json.dumps(row) + "\n")
            out.flush()
            if n % 500 == 0:
                print(f"{n:,}/{len(todo):,} fetched", flush=True)
            time.sleep(DELAY)
    print("done", flush=True)


if __name__ == "__main__":
    main()
