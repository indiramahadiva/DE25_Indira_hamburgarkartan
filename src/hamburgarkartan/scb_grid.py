"""Download SCB's population per 1 km grid cell and load it into DuckDB."""

import time
from pathlib import Path

import duckdb
import requests

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "warehouse" / "hamburgarkartan.duckdb"

YEAR = 2025  # newest year SCB publishes
WFS_URL = "https://geodata.scb.se/geoserver/stat/wfs"
HEADERS = {"User-Agent": "hamburgarkartan-student-project"}


def download_grid(year=YEAR):
    """Download the grid as a GeoPackage. Skip if it's already downloaded."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"scb_befolkning_1km_{year}.gpkg"
    if path.exists():
        print("Already downloaded:", path.name)
        return path

    params = {
        "service": "WFS",
        "request": "GetFeature",
        "version": "1.1.0",
        "typeNames": f"stat:befolkning_1km_{year}",
        "outputFormat": "geopackage",
    }
    temp = path.with_suffix(".part")
    print(
        f"Downloading SCB grid {year} (the server builds the file first, can take a while) ..."
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
            text = temp.read_text(errors="replace")[:500]
            temp.unlink()
            raise RuntimeError(f"Not a GeoPackage, server said:\n{text}")

    temp.rename(path)
    print("\nSaved:", path.name)
    return path


def load_grid(gpkg_path):
    """Load the GeoPackage as-is into raw.scb_grid_1km."""
    start = time.perf_counter()
    con = duckdb.connect(str(DB_PATH))
    con.install_extension("spatial")
    con.load_extension("spatial")
    con.sql("CREATE SCHEMA IF NOT EXISTS raw")

    con.sql(f"""
        CREATE OR REPLACE TABLE raw.scb_grid_1km AS
        SELECT
            *,
            '{gpkg_path.name}' AS _source,
            current_timestamp AS _loaded_at
        FROM ST_Read('{gpkg_path.as_posix()}')
    """)

    count = con.sql("SELECT count(*) FROM raw.scb_grid_1km").fetchone()[0]
    print(f"Grid cells loaded: {count} ({time.perf_counter() - start:.0f} s)")
    con.close()


if __name__ == "__main__":
    load_grid(download_grid())
