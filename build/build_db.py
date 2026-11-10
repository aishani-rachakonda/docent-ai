"""Offline build, step 1: turn the Met's Open Access CSV into data/met.duckdb.

Keeps only objects with a gallery number (the CSV's sign that an object is on view), cleans the
columns the agent reasons with, and adds empty columns that later build steps fill in:
image links (fetch_images.py) and Wikipedia article titles (wikidata_titles.py).

    uv run build/build_db.py
"""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "raw" / "MetObjects.csv"
DB = ROOT / "data" / "met.duckdb"


def build() -> None:
    con = duckdb.connect(str(DB))
    # Read every column as text: the CSV mixes types, pads years with spaces, and uses "" for missing
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE raw AS
        SELECT * FROM read_csv('{CSV}', all_varchar = true, header = true, quote = '"', escape = '"',
                               max_line_size = 10000000)
    """)
    # Keep the existing image and Wikipedia columns if the table is being rebuilt
    old = {}
    if con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'objects'").fetchone()[0]:
        old_cols = {r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'objects'").fetchall()}
        if "image_url" in old_cols:
            con.execute("CREATE OR REPLACE TEMP TABLE old_extra AS SELECT object_id, image_url, image_small_url, image_checked_at, api_on_view, api_gallery FROM objects")
            old["images"] = True

    con.execute("""
        CREATE OR REPLACE TABLE objects AS
        SELECT
            CAST("Object ID" AS INTEGER)                     AS object_id,
            trim("Object Number")                             AS accession_number,
            nullif(trim("Title"), '')                         AS title,
            nullif(trim("Object Name"), '')                   AS object_name,
            -- Several makers are joined with '|' in the CSV; keep the first as the main artist
            nullif(trim(split_part("Artist Display Name", '|', 1)), '') AS artist,
            nullif(trim("Artist Display Name"), '')           AS all_artists,
            nullif(trim(split_part("Artist Display Bio", '|', 1)), '') AS artist_bio,
            nullif(trim(split_part("Artist Nationality", '|', 1)), '') AS artist_nationality,
            nullif(trim(split_part("Artist Role", '|', 1)), '') AS artist_role,
            nullif(trim("Culture"), '')                       AS culture,
            nullif(trim("Period"), '')                        AS period,
            nullif(trim("Dynasty"), '')                       AS dynasty,
            nullif(trim("Reign"), '')                         AS reign,
            nullif(trim("Object Date"), '')                   AS object_date,
            TRY_CAST(trim("Object Begin Date") AS INTEGER)    AS begin_year,
            TRY_CAST(trim("Object End Date") AS INTEGER)      AS end_year,
            nullif(trim("Medium"), '')                        AS medium,
            nullif(trim("Dimensions"), '')                    AS dimensions,
            nullif(trim("Classification"), '')                AS classification,
            nullif(trim("Department"), '')                    AS department,
            trim("Gallery Number")                            AS gallery,
            nullif(trim(concat_ws(', ', nullif(trim("City"), ''), nullif(trim("State"), ''),
                                  nullif(trim("Country"), ''), nullif(trim("Region"), ''))), '') AS place,
            nullif(trim("Country"), '')                       AS country,
            nullif(trim("Credit Line"), '')                   AS credit_line,
            "Is Highlight" = 'True'                           AS is_highlight,
            "Is Timeline Work" = 'True'                       AS is_timeline_work,
            "Is Public Domain" = 'True'                       AS is_public_domain,
            -- Tags are '|'-separated subject keywords, e.g. 'Cats|Women'
            CASE WHEN trim("Tags") = '' OR "Tags" IS NULL THEN []::VARCHAR[]
                 ELSE list_transform(string_split("Tags", '|'), lambda t: trim(t)) END AS tags,
            nullif(trim("Link Resource"), '')                 AS met_url,
            nullif(regexp_extract("Object Wikidata URL", 'Q[0-9]+'), '') AS object_qid,
            nullif(regexp_extract(split_part("Artist Wikidata URL", '|', 1), 'Q[0-9]+'), '') AS artist_qid,
            TRY_STRPTIME(trim("Metadata Date"), '%m/%d/%Y %I:%M:%S %p') AS metadata_date
        FROM raw
        WHERE trim(coalesce("Gallery Number", '')) <> ''
    """)

    # Columns later build steps fill in
    con.execute("""
        ALTER TABLE objects ADD COLUMN image_url VARCHAR;
        ALTER TABLE objects ADD COLUMN image_small_url VARCHAR;
        ALTER TABLE objects ADD COLUMN image_checked_at TIMESTAMP;
        ALTER TABLE objects ADD COLUMN api_on_view BOOLEAN;
        ALTER TABLE objects ADD COLUMN api_gallery VARCHAR;
    """)
    if old.get("images"):
        con.execute("""
            UPDATE objects o SET image_url = x.image_url, image_small_url = x.image_small_url,
                   image_checked_at = x.image_checked_at, api_on_view = x.api_on_view, api_gallery = x.api_gallery
            FROM old_extra x WHERE o.object_id = x.object_id
        """)

    # One searchable line of text per object, for keyword and embedding search
    con.execute("""
        ALTER TABLE objects ADD COLUMN search_text VARCHAR;
        UPDATE objects SET search_text = concat_ws(' | ',
            title, object_name, artist, artist_nationality, culture, period, dynasty, object_date,
            medium, classification, department, place, array_to_string(tags, ', '));
    """)

    con.execute("CREATE TABLE IF NOT EXISTS build_info (key VARCHAR PRIMARY KEY, value VARCHAR)")
    con.execute("INSERT OR REPLACE INTO build_info VALUES ('csv_built_at', CAST(now() AS VARCHAR))")
    con.execute("INSERT OR REPLACE INTO build_info SELECT 'csv_latest_metadata_date', CAST(max(metadata_date) AS VARCHAR) FROM objects")

    total = con.execute("SELECT count(*) FROM raw").fetchone()[0]
    print(f"CSV rows: {total:,}")
    print(con.execute("""
        SELECT count(*) AS on_view, count(DISTINCT gallery) AS galleries,
               count(*) FILTER (is_public_domain) AS public_domain,
               count(*) FILTER (is_highlight) AS highlights,
               count(object_qid) AS object_wikidata, count(artist_qid) AS artist_wikidata,
               count(*) FILTER (len(tags) > 0) AS tagged,
               count(DISTINCT accession_number) AS distinct_accessions,
               min(metadata_date) AS oldest_update, max(metadata_date) AS newest_update
        FROM objects
    """).df().T.to_string(header=False))
    con.close()


if __name__ == "__main__":
    build()
