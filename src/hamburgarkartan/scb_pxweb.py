"""Fetch municipality statistics from SCB's PxWebApi v2 and load them into DuckDB."""

import json
import time
from datetime import date
from itertools import product
from pathlib import Path

import duckdb
import requests

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "warehouse" / "hamburgarkartan.duckdb"

API = "https://statistikdatabasen.scb.se/api/v2"
HEADERS = {"User-Agent": "hamburgarkartan-student-project"}

YEAR = "2025"  # same year as the SCB population grid

# Tables to fetch: {name: (table_id, selection)}. Found with search_tables() /
# show_metadata() in notebook 03. "*" = all values.
TABLES = {
    # TAB628: population density, population and land area per region and sex
    "kommun_stats": (
        "TAB628",
        {
            "Region": [
                "*"
            ],  # Sweden (00) + 21 counties + 290 municipalities; filtered in dbt
            "Kon": ["1+2"],  # both sexes together
            "ContentsCode": [
                "BE0101U1",  # inhabitants per km²
                "BE0101U2",  # population
                "BE0101U3",  # land area, km²
            ],
            "Tid": [YEAR],
        },
    ),
}


# ---------- talking to the API ----------


def _get(url, **kwargs):
    """GET/POST with a polite retry when SCB says "too many requests" (HTTP 429)."""
    method = kwargs.pop("method", "GET")
    for attempt in range(5):
        response = requests.request(method, url, headers=HEADERS, timeout=60, **kwargs)
        if response.status_code == 429:  # limit: about 30 calls per 10 seconds
            print("Too many requests, waiting 10 s ...")
            time.sleep(10)
            continue
        if response.status_code >= 400:
            raise RuntimeError(
                f"{response.status_code} from SCB: {response.text[:500]}"
            )
        return response.json()
    raise RuntimeError("SCB kept answering 429 – try again later")


def search_tables(query, lang="sv"):
    """Search SCB's tables by words, e.g. search_tables("folkmängd kommun")."""
    data = _get(f"{API}/tables", params={"query": query, "lang": lang, "pageSize": 30})
    for t in data.get("tables", []):
        print(
            f"{t['id']:<9} {t.get('firstPeriod', '')}–{t.get('lastPeriod', '')}  {t['label']}"
        )


def show_metadata(table_id, lang="sv", max_values=8):
    """Print the dimensions of a table and a few of their values."""
    meta = _get(f"{API}/tables/{table_id}/metadata", params={"lang": lang})
    print(meta.get("label", table_id))
    for dim_id in meta["id"]:
        labels = meta["dimension"][dim_id]["category"]["label"]
        values = list(labels.items())
        print(f"\n{dim_id}  ({len(values)} values)")
        for code, label in values[:max_values]:
            print(f"   {code:<12} {label}")
        if len(values) > max_values:
            print("   ...")


def fetch_table(table_id, selection, lang="sv"):
    """Download one table as JSON-stat2. selection = {variable: [value codes]}."""
    body = {
        "selection": [
            {"variableCode": var, "valueCodes": codes}
            for var, codes in selection.items()
        ]
    }
    return _get(
        f"{API}/tables/{table_id}/data",
        method="POST",
        params={"lang": lang, "outputFormat": "json-stat2"},
        json=body,
    )


# ---------- JSON-stat2 -> rows ----------


def jsonstat_to_rows(js):
    """Turn a JSON-stat2 cube into one dict per cell (long format).

    JSON-stat stores all numbers in one flat list `value`, ordered like
    nested loops over the dimensions in `id`. We rebuild that loop.
    """
    dims = js["id"]
    codes_per_dim = []
    for dim_id in dims:
        index = js["dimension"][dim_id]["category"]["index"]
        # index is either {code: position} or a list of codes
        codes = sorted(index, key=index.get) if isinstance(index, dict) else list(index)
        codes_per_dim.append(codes)

    values = js["value"]
    if isinstance(values, dict):  # sparse form {position: value}
        values = [values.get(str(i)) for i in range(_cube_size(codes_per_dim))]

    rows = []
    for position, combo in enumerate(product(*codes_per_dim)):
        row = {}
        for dim_id, code in zip(dims, combo):
            label = js["dimension"][dim_id]["category"].get("label", {}).get(code, code)
            row[dim_id] = code
            row[f"{dim_id}_label"] = label
        row["value"] = values[position]
        rows.append(row)
    return rows


def _cube_size(codes_per_dim):
    size = 1
    for codes in codes_per_dim:
        size *= len(codes)
    return size


# ---------- save and load ----------
# Always read and write files as UTF-8. Windows otherwise uses its own
# encoding (cp1252), which breaks names like "Österåker" for DuckDB.


def download_all():
    """Fetch every table in TABLES and save the raw JSON (one file per table)."""
    if not TABLES:
        raise RuntimeError("TABLES is empty – fill it in first (see notebook 03).")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, (table_id, selection) in TABLES.items():
        path = RAW_DIR / f"scb_{name}_{table_id}_{date.today()}.json"
        if path.exists():
            print("Already downloaded:", path.name)
        else:
            print(f"Fetching {name} ({table_id}) ...")
            path.write_text(
                json.dumps(fetch_table(table_id, selection), ensure_ascii=False),
                encoding="utf-8",
            )
            print("Saved:", path.name)
        paths[name] = (table_id, path)
    return paths


def load_all(paths):
    """Load each saved table into raw.scb_<name> in long format."""
    con = duckdb.connect(str(DB_PATH))
    con.sql("CREATE SCHEMA IF NOT EXISTS raw")
    for name, (table_id, path) in paths.items():
        rows = jsonstat_to_rows(json.loads(path.read_text(encoding="utf-8")))
        for row in rows:
            row["_table_id"] = table_id
            row["_source"] = path.name
        tmp = path.with_suffix(".rows.json")  # temporary file for DuckDB to read
        tmp.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        try:
            con.sql(f"""
                CREATE OR REPLACE TABLE raw.scb_{name} AS
                SELECT *, current_timestamp AS _loaded_at
                FROM read_json_auto('{tmp.as_posix()}')
            """)
        finally:
            tmp.unlink()  # removed even if loading fails
        print(f"raw.scb_{name}: {len(rows)} rows")
    con.close()


if __name__ == "__main__":
    load_all(download_all())
