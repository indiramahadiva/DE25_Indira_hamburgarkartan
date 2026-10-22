"""Download Sweden's OSM data from Geofabrik and extract food places into DuckDB."""

from datetime import date
from pathlib import Path

import duckdb
import requests

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "warehouse" / "hamburgarkartan.duckdb"

URL = "https://download.geofabrik.de/europe/sweden-latest.osm.pbf"
HEADERS = {"User-Agent": "hamburgarkartan-student-project"}


def download_sweden():
    """Download today's Sweden file. Skip if it's already downloaded."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"sweden_{date.today()}.osm.pbf"
    if path.exists():
        print("Already downloaded:", path.name)
        return path

    temp = path.with_suffix(".part")  # unfinished download gets a different name
    with requests.get(URL, stream=True, headers=HEADERS, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        done = 0
        with open(temp, "wb") as f:
            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):  # 1 MB at a time
                f.write(chunk)
                done += len(chunk)
                print(f"\rDownloading: {done / 1e6:.0f} / {total / 1e6:.0f} MB", end="")
    temp.rename(path)  # only renamed when complete -> never a half file
    print("\nSaved:", path.name)
    return path


def extract_food_places(pbf_path):
    """Read the OSM file and store all fast food places and restaurants in raw.osm_food_places."""
    con = duckdb.connect(str(DB_PATH))
    con.install_extension("spatial")
    con.load_extension("spatial")
    con.sql("CREATE SCHEMA IF NOT EXISTS raw")

    con.sql(f"""
        CREATE OR REPLACE TABLE raw.osm_food_places AS
        WITH osm AS (
            SELECT kind, id, tags, refs, lat, lon
            FROM ST_ReadOSM('{pbf_path.as_posix()}')
        ),
        food AS (
            -- points and buildings tagged as fast food or restaurant
            SELECT * FROM osm
            WHERE kind IN ('node', 'way')
              AND tags['amenity'] IN ('fast_food', 'restaurant')
        ),
        way_corners AS (
            -- a building only lists its corner node IDs, not coordinates
            SELECT DISTINCT id AS way_id, unnest(refs) AS node_id
            FROM food WHERE kind = 'way'
        ),
        way_centers AS (
            -- look up each corner's coordinates and average them -> center point
            SELECT c.way_id, avg(n.lat) AS lat, avg(n.lon) AS lon
            FROM way_corners c
            JOIN osm n ON n.kind = 'node' AND n.id = c.node_id
            GROUP BY c.way_id
        )
        SELECT
            f.kind::VARCHAR AS osm_type,
            f.id AS osm_id,
            coalesce(f.lat, w.lat) AS lat,
            coalesce(f.lon, w.lon) AS lon,
            f.tags,
            '{pbf_path.name}' AS source_file
        FROM food f
        LEFT JOIN way_centers w ON f.kind = 'way' AND w.way_id = f.id
    """)

    con.sql(
        "DROP TABLE IF EXISTS raw.osm_fast_food"
    )  # old name, replaced by osm_food_places

    count = con.sql("SELECT count(*) FROM raw.osm_food_places").fetchone()[0]
    print("Food places in Sweden:", count)
    con.close()


def remove_old_files(keep=2):
    """Keep only the newest files, delete older ones to save disk space."""
    files = sorted(RAW_DIR.glob("sweden_*.osm.pbf"))
    for old in files[:-keep]:
        old.unlink()
        print("Removed old file:", old.name)


if __name__ == "__main__":
    extract_food_places(download_sweden())
    remove_old_files(keep=2)
