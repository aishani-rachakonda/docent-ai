"""Copy the image crawl (data/raw/images.jsonl) into the database.

Fills image_url, image_small_url, image_checked_at, api_gallery and api_on_view on `objects`.
The API's gallery is what the Met showed when we asked; the CSV's gallery is from its last export.
plan_route still checks each tour stop live, so these columns only need to be close.

    uv run build/merge_images.py
"""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "met.duckdb"
CRAWL = ROOT / "data" / "raw" / "images.jsonl"


def main() -> None:
    con = duckdb.connect(str(DB))
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE crawl AS
        SELECT object_id::BIGINT AS object_id, status, fetched_at::TIMESTAMPTZ AS fetched_at,
               nullif(image_url, '') AS image_url, nullif(image_small_url, '') AS image_small_url,
               nullif(trim(gallery), '') AS gallery
        FROM read_json('{CRAWL}', format='newline_delimited',
                       columns={{object_id: 'BIGINT', status: 'INTEGER', fetched_at: 'VARCHAR',
                                 image_url: 'VARCHAR', image_small_url: 'VARCHAR', gallery: 'VARCHAR'}})
        QUALIFY row_number() OVER (PARTITION BY object_id ORDER BY fetched_at DESC) = 1""")
    con.execute("""
        UPDATE objects o SET
            image_url = c.image_url,
            image_small_url = c.image_small_url,
            image_checked_at = c.fetched_at,
            api_gallery = c.gallery,
            api_on_view = c.gallery IS NOT NULL
        FROM crawl c
        WHERE o.object_id::BIGINT = c.object_id AND c.status = 200""")
    con.execute("""INSERT OR REPLACE INTO build_info VALUES
        ('images_checked_at', (SELECT max(fetched_at)::VARCHAR FROM crawl))""")
    print(con.execute("""
        SELECT count(*) AS on_view,
               count(image_checked_at) AS checked,
               count(image_url) AS with_image,
               count(*) FILTER (WHERE image_url IS NOT NULL AND is_public_domain) AS with_image_public_domain,
               count(*) FILTER (WHERE api_on_view = false) AS api_says_off_view,
               count(*) FILTER (WHERE api_gallery IS NOT NULL AND api_gallery <> gallery) AS moved
        FROM objects""").df().to_string(index=False))
    con.close()


if __name__ == "__main__":
    main()
