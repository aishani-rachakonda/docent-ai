"""Read-only queries over data/met.duckdb: the facts every agent works from.

Plain functions that return JSON-able dicts, so they can be tested without a model and wrapped as
agent tools in app.py. Every object a function returns carries its Met URL, so the Writer can cite it.
"""

import re
import threading
from pathlib import Path

import duckdb

DB = Path(__file__).parent / "data" / "met.duckdb"
_local = threading.local()

# Columns an agent sees for one object in a list. Short on purpose: lists can be long.
BRIEF = """object_id, accession_number, title, artist, object_date, culture, department, gallery,
           is_highlight, met_url"""


def db() -> duckdb.DuckDBPyConnection:
    """One read-only connection per thread: DuckDB connections are not safe to share across threads."""
    if not hasattr(_local, "con"):
        _local.con = duckdb.connect(str(DB), read_only=True)
    return _local.con


def _rows(sql: str, params: list | None = None) -> list[dict]:
    cur = db().execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def snapshot_info() -> dict:
    """When the data was built and how fresh the Met's own records are."""
    raw = {k: v for k, v in db().execute("SELECT key, value FROM build_info").fetchall()}
    return {
        # The date to quote: the newest change in the Met's own records, not when we built the file
        "data_as_of": (raw.get("csv_latest_metadata_date") or "")[:10],
        "snapshot_built": (raw.get("csv_built_at") or "")[:10],
        "objects_on_view": db().execute("SELECT count(*) FROM objects").fetchone()[0],
    }


# --- Identify one object (the label reader) ---

# Characters a camera or a person commonly misreads in an accession number
_CONFUSABLE = str.maketrans({"l": "1", "I": "1", "i": "1", "|": "1", "O": "0", "o": "0", ",": ".", " ": ""})


def _normalize(acc: str) -> str:
    return acc.strip().translate(_CONFUSABLE).lower().replace("–", "-").replace("—", "-")


def find_by_accession(accession: str, title_hint: str = "", artist_hint: str = "") -> dict:
    """Find the object with this accession number, as read from a wall label.

    Tries an exact match, then a match after fixing common misreadings (l/1, O/0), then numbers one
    character away. A near match is only a candidate: it is confirmed when the title or artist hint
    agrees with the record. Returns {status, matches, note}.
    """
    acc = accession.strip()
    hints = [h.lower().strip() for h in (title_hint, artist_hint) if h and h.strip()]

    def agrees(r: dict) -> bool:
        text = f"{r['title'] or ''} {r['artist'] or ''}".lower()
        return any(h in text or (r["title"] and r["title"].lower() in h) for h in hints)

    norm = _normalize(acc)
    exact = _rows(f"SELECT {BRIEF} FROM objects WHERE accession_number = ?", [acc])
    fixed = exact or _rows(f"""SELECT {BRIEF} FROM objects
                                WHERE lower(replace(accession_number, ' ', '')) = ?""", [norm])
    # A misread number can land on a different, real object (1993.132 read as 1993.13 is
    # Henry Kirke Brown's 'Filatrice', not van Gogh). With hints, a match must agree with them.
    if fixed and (not hints or any(agrees(r) for r in fixed)):
        if exact:
            return {"status": "exact", "matches": exact, "note": "Accession number matched exactly."
                    + ("" if hints else " No title or artist was given to cross-check it.")}
        return {"status": "corrected", "matches": fixed,
                "note": f"No exact match for '{acc}'; matched after correcting likely misreadings to '{norm}'."}
    mismatch = fixed  # a real object, but not the one the label describes

    # One character away (a dropped, extra or misread character). Several can tie, so use the hints.
    near = _rows(f"""SELECT {BRIEF}, levenshtein(lower(accession_number), ?) AS distance FROM objects
                     WHERE abs(length(accession_number) - length(?)) <= 1
                       AND levenshtein(lower(accession_number), ?) <= 1
                       AND accession_number <> ?
                     ORDER BY distance LIMIT 10""", [norm, norm, norm, acc])
    if hints:
        confirmed = [r for r in near if agrees(r)]
        if len(confirmed) == 1:
            return {"status": "near_confirmed", "matches": confirmed,
                    "note": f"'{acc}' is one character off from {confirmed[0]['accession_number']}, and the title/artist on the label agree."
                            + (f" ('{acc}' itself is a different object: {mismatch[0]['title']}.)" if mismatch else "")}
    if mismatch:
        return {"status": "mismatch", "matches": mismatch + near,
                "note": f"'{acc}' exists, but it is '{mismatch[0]['title']}', which does not match the label's "
                        "title/artist. The number was probably misread; do not name an object until it is confirmed."}
    if near:
        return {"status": "ambiguous", "matches": near,
                "note": f"No object has accession number '{acc}'. These are one character away; none is confirmed. "
                        "Ask the visitor for the title or artist on the label before naming the object."}
    return {"status": "not_found", "matches": [],
            "note": f"No on-view object has accession number '{acc}' or anything close. It may be a loan, "
                    "in a special exhibition, recently moved, or misread."}


def find_by_title(title: str, artist: str = "", limit: int = 10) -> dict:
    """Find on-view objects by the title (and optionally artist) on a label, when there is no number."""
    sql = f"""SELECT {BRIEF}, jaro_winkler_similarity(lower(title), lower(?)) AS score FROM objects
              WHERE title ILIKE ? OR jaro_winkler_similarity(lower(title), lower(?)) > 0.9"""
    params = [title, f"%{title}%", title]
    if artist:
        sql += " AND (artist ILIKE ? OR all_artists ILIKE ?)"
        params += [f"%{artist}%", f"%{artist}%"]
    sql += " ORDER BY score DESC, is_highlight DESC LIMIT ?"
    rows = _rows(sql, params + [limit])
    return {"count": len(rows), "matches": rows,
            "note": "Several objects can share a title (e.g. 'Virgin and Child'); confirm with the artist or gallery."}


# --- Look up and search ---

def get_object(object_id: int) -> dict:
    """Everything the snapshot knows about one object, including its Wikipedia article titles if any."""
    rows = _rows("""
        SELECT o.* EXCLUDE (search_text),
               ow.enwiki_title AS object_wikipedia, ow.description AS object_wikidata_description,
               aw.enwiki_title AS artist_wikipedia
        FROM objects o
        LEFT JOIN (SELECT * FROM wiki) ow ON ow.qid = o.object_qid
        LEFT JOIN (SELECT * FROM wiki) aw ON aw.qid = o.artist_qid
        WHERE o.object_id = ?""", [object_id]) if _has_wiki() else _rows(
        "SELECT * EXCLUDE (search_text) FROM objects WHERE object_id = ?", [object_id])
    if not rows:
        return {"error": f"Object {object_id} is not in the on-view snapshot."}
    row = rows[0]
    return {k: (str(v) if k.endswith(("_at", "_date")) and v is not None else v) for k, v in row.items()}


def _has_wiki() -> bool:
    if not hasattr(_local, "has_wiki"):
        _local.has_wiki = bool(db().execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = 'wiki'").fetchone()[0])
    return _local.has_wiki


def search_objects(keywords: str = "", department: str = "", gallery: str = "", culture: str = "",
                   artist: str = "", begin_year: int | None = None, end_year: int | None = None,
                   highlights_only: bool = False, with_image: bool = False, per_gallery: int = 3,
                   limit: int = 25) -> dict:
    """Search on-view objects by keywords and filters.

    keywords: words matched against title, artist, culture, medium, tags and more. Every word must
    match somewhere (so use few, specific words). per_gallery caps how many results come from one
    gallery, so a few crowded study galleries can't fill the list.
    """
    where, params = [], []
    for word in re.findall(r"[\w'-]+", keywords.lower()):
        # Whole words (plus plurals), so 'cat' finds 'Cats' but not 'Catalan'
        where.append("regexp_matches(search_text, ?)")
        params.append(rf"(?i)\b{re.escape(word)}(s|es)?\b")
    for col, val in (("department", department), ("culture", culture)):
        if val:
            where.append(f"{col} ILIKE ?")
            params.append(f"%{val}%")
    if artist:
        where.append("all_artists ILIKE ?")
        params.append(f"%{artist}%")
    if gallery:
        where.append("gallery = ?")
        params.append(str(gallery))
    if begin_year is not None:
        where.append("end_year >= ?")
        params.append(begin_year)
    if end_year is not None:
        where.append("begin_year <= ?")
        params.append(end_year)
    if highlights_only:
        where.append("is_highlight")
    if with_image:
        where.append("image_small_url IS NOT NULL")
    cond = " AND ".join(where) or "TRUE"
    total = db().execute(f"SELECT count(*) FROM objects WHERE {cond}", params).fetchone()[0]
    rows = _rows(f"""
        SELECT * EXCLUDE (rank_in_gallery) FROM (
            SELECT {BRIEF}, image_small_url IS NOT NULL AS has_image,
                   row_number() OVER (PARTITION BY gallery ORDER BY is_highlight DESC, len(tags) DESC, object_id)
                       AS rank_in_gallery
            FROM objects WHERE {cond})
        WHERE rank_in_gallery <= ?
        ORDER BY is_highlight DESC, has_image DESC, gallery
        LIMIT ?""", params + [per_gallery, limit])
    return {"total_matches": total, "returned": len(rows), "objects": rows}


def gallery_summary(gallery: str) -> dict:
    """What a gallery holds: object count, departments, cultures, dates, and its highlights."""
    g = str(gallery).strip()
    stats = _rows("""
        SELECT count(*) AS objects_on_view, list(DISTINCT department) AS departments,
               min(begin_year) AS earliest_year, max(end_year) AS latest_year,
               count(*) FILTER (is_highlight) AS highlights
        FROM objects WHERE gallery = ?""", [g])[0]
    if not stats["objects_on_view"]:
        return {"error": f"No on-view objects are recorded in gallery '{g}'."}
    stats["top_cultures"] = _rows("""SELECT culture, count(*) AS n FROM objects WHERE gallery = ? AND culture IS NOT NULL
                                     GROUP BY 1 ORDER BY n DESC LIMIT 5""", [g])
    stats["highlight_objects"] = _rows(f"""SELECT {BRIEF} FROM objects WHERE gallery = ?
                                          ORDER BY is_highlight DESC, len(tags) DESC LIMIT 8""", [g])
    stats["gallery"] = g
    return stats


# --- Explorer: read-only SQL for counting and comparing ---

SCHEMA = """Table objects (one row per object on view at the Met):
  object_id INT, accession_number, title, object_name, artist (first maker), all_artists ('|'-joined),
  artist_bio, artist_nationality, artist_role, culture, period, dynasty, reign, object_date (text),
  begin_year INT, end_year INT (negative = BCE), medium, dimensions, classification, department,
  gallery (text, e.g. '822'), place, country, credit_line, is_highlight BOOL, is_timeline_work BOOL,
  is_public_domain BOOL, tags VARCHAR[] (subject keywords, e.g. ['Cats','Women']), met_url,
  image_small_url (NULL if no open-access image), metadata_date TIMESTAMP.
Use ILIKE for text, list_contains(tags, 'Cats') for tags. Gallery is text."""

_FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|create|alter|attach|copy|export|install|load|pragma|set|call)\b", re.I)


def run_sql(sql: str, max_rows: int = 50) -> dict:
    """Run one read-only SELECT over the snapshot. For counts, comparisons and rankings."""
    stripped = sql.strip().rstrip(";")
    if not re.match(r"(?is)^\s*(with|select)\b", stripped) or ";" in stripped or _FORBIDDEN.search(stripped):
        return {"error": "Only a single read-only SELECT (or WITH ... SELECT) is allowed."}
    try:
        cur = db().execute(stripped)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(max_rows + 1)
    except duckdb.Error as e:
        return {"error": f"{type(e).__name__}: {e}", "schema": SCHEMA}
    return {"columns": cols, "rows": [list(map(_jsonable, r)) for r in rows[:max_rows]],
            "truncated": len(rows) > max_rows}


def _jsonable(v):
    return v if isinstance(v, (str, int, float, bool, type(None), list)) else str(v)
