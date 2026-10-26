"""Download SCB's DeSO areas and load them into DuckDB.

SCB has no layer with municipality borders in its WFS service, but every
DeSO area lies inside exactly one municipality, and the first four
characters of the DeSO code are the municipality code. Merging the DeSO
areas per municipality code (done later in dbt) gives the 290 municipalities.
"""

import time
from pathlib import Path

import duckdb
import requests

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "warehouse" / "hamburgarkartan.duckdb"

WFS_URL = "https://geodata.scb.se/geoserver/stat/wfs"
LAYER = "stat:DeSO_2025"  # newest DeSO division, matches the 2025 statistics
HEADERS = {"User-Agent": "hamburgarkartan-student-project"}


def download_deso(layer=LAYER):
    """Download the DeSO layer as a GeoPackage. Skip if it's already downloaded."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"scb_{layer.split(':')[1].lower()}.gpkg"
    if path.exists():
        print("Already downloaded:", path.name)
        return path

    params = {
        "service": "WFS",
        "request": "GetFeature",
        "version": "1.1.0",
        "typeNames": layer,
        "outputFormat": "geopackage",
    }
    temp = path.with_suffix(".part")
    print(
        f"Downloading {layer} (the server builds the file first, can take a while) ..."
    )
    with requests.get(
        WFS_URL, params=params, stream=True, headers=HEADERS, timeout=600
    ) as response:
        response.raise_for_status()
        done = 0
        with open(temp, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1 MB
                f.write(chunk)
                done += len(chunk)
                print(f"\rDownloaded: {done / 1e6:.0f} MB", end="")

    # A WFS error comes back as a small XML text, not a GeoPackage -> check before keeping it
    with open(temp, "rb") as f:
        if not f.read(16).startswith(b"SQLite format 3"):
            text = temp.read_text(encoding="utf-8", errors="replace")[:500]
            temp.unlink()
            raise RuntimeError(f"Not a GeoPackage, server said:\n{text}")

    temp.rename(path)
    print("\nSaved:", path.name)
    return path


def load_deso(gpkg_path):
    """Load the GeoPackage as-is into raw.scb_deso."""
    start = time.perf_counter()
    con = duckdb.connect(str(DB_PATH))
    con.install_extension("spatial")
    con.load_extension("spatial")
    con.sql("CREATE SCHEMA IF NOT EXISTS raw")

    con.sql(f"""
        CREATE OR REPLACE TABLE raw.scb_deso AS
        SELECT
            *,
            '{gpkg_path.name}' AS _source,
            current_timestamp AS _loaded_at
        FROM ST_Read('{gpkg_path.as_posix()}')
    """)

    count = con.sql("SELECT count(*) FROM raw.scb_deso").fetchone()[0]
    print(f"DeSO areas loaded: {count} ({time.perf_counter() - start:.0f} s)")
    con.close()


if __name__ == "__main__":
    load_deso(download_deso())
