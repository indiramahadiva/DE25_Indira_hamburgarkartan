"""Download Sweden's OSM data from Geofabrik and extract food places into DuckDB."""

import time
from datetime import date
from pathlib import Path

import duckdb
import requests

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "warehouse" / "hamburgarkartan.duckdb"

URL = "https://download.geofabrik.de/europe/sweden-latest.osm.pbf"
HEADERS = {"User-Agent": "hamburgarkartan-student-project"}

# Brands we always keep, even if the place is not tagged as fast_food/restaurant
# (e.g. a Sibylla inside a petrol station). Lowercase regex.
CHAIN_BRANDS = "mcdonald|burger king|sibylla|max burgers|^max$"


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
            for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1 MB
                f.write(chunk)
                done += len(chunk)
                print(f"\rDownloading: {done / 1e6:.0f} / {total / 1e6:.0f} MB", end="")
    temp.rename(path)  # only renamed when complete -> never a half file
    print("\nSaved:", path.name)
    return path


def extract_food_places(pbf_path):
    """Read the OSM file and store fast food places and restaurants in raw.osm_food_places.

    Two passes over the file instead of one big query:
      1. keep only food places (small table)
      2. look up coordinates only for the nodes those buildings (ways) need
    This avoids holding every node in Sweden in memory.
    """
    start = time.perf_counter()
    src = pbf_path.as_posix()

    con = duckdb.connect(str(DB_PATH))
    con.install_extension("spatial")
    con.load_extension("spatial")
    con.sql("SET preserve_insertion_order = false")  # less memory, order not needed
    con.sql("CREATE SCHEMA IF NOT EXISTS raw")

    # Pass 1: food places (points and buildings)
    print("Pass 1/2: finding food places ...")
    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE food AS
        SELECT kind::VARCHAR AS osm_type, id AS osm_id, tags, refs, lat, lon
        FROM ST_ReadOSM('{src}')
        WHERE kind IN ('node', 'way')
          AND (
              tags['amenity'] IN ('fast_food', 'restaurant')
              OR regexp_matches(lower(tags['brand']), '{CHAIN_BRANDS}')
          )
    """)
    print(
        f"  found {con.sql('SELECT count(*) FROM food').fetchone()[0]} places "
        f"({time.perf_counter() - start:.0f} s)"
    )

    # A building (way) only lists its corner node IDs, not coordinates
    con.sql("""
        CREATE OR REPLACE TEMP TABLE way_nodes AS
        SELECT DISTINCT osm_id AS way_id, unnest(refs) AS node_id
        FROM food
        WHERE osm_type = 'way'
    """)

    # Pass 2: coordinates for just those corner nodes
    print("Pass 2/2: looking up building corners ...")
    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE node_coords AS
        SELECT id AS node_id, lat, lon
        FROM ST_ReadOSM('{src}')
        WHERE kind = 'node'
          AND id IN (SELECT node_id FROM way_nodes)
    """)

    # Average the corners -> center point of each building, then save
    con.sql(f"""
        CREATE OR REPLACE TABLE raw.osm_food_places AS
        WITH way_centers AS (
            SELECT w.way_id, avg(n.lat) AS lat, avg(n.lon) AS lon
            FROM way_nodes w
            JOIN node_coords n USING (node_id)
            GROUP BY w.way_id
        )
        SELECT
            f.osm_type,
            f.osm_id,
            coalesce(f.lat, c.lat) AS lat,
            coalesce(f.lon, c.lon) AS lon,
            f.tags,
            '{pbf_path.name}' AS _source,
            current_timestamp AS _loaded_at
        FROM food f
        LEFT JOIN way_centers c ON f.osm_type = 'way' AND c.way_id = f.osm_id
    """)

    count = con.sql("SELECT count(*) FROM raw.osm_food_places").fetchone()[0]
    print(f"Food places in Sweden: {count} ({time.perf_counter() - start:.0f} s total)")
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
