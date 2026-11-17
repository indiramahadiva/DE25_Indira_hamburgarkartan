"""Get kommun stats from SCB's API and put them in DuckDB."""

import json
import time
from datetime import date
from itertools import product
from pathlib import Path

import duckdb
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]  # project folder, two levels up
RAW_DIR = ROOT / "data" / "raw"  # downloaded files go here
DB_PATH = ROOT / "warehouse" / "hamburgarkartan.duckdb"  # the database

API = "https://statistikdatabasen.scb.se/api/v2"
HEADERS = {"User-Agent": "hamburgarkartan-student-project"}  # tells SCB who's asking

YEAR = "2025"  # same year as the population grid

# What to fetch: {my name: (SCB table, which parts of it)}.
# Found with search_tables() and show_metadata() in notebook 03. "*" = everything.
TABLES = {
    # TAB628 = population, land area and density per region
    "kommun_stats": (
        "TAB628",
        {
            "Region": ["*"],  # all regions – dbt keeps only the 290 kommuner
            "Kon": ["1+2"],  # men and women together
            "ContentsCode": [
                "BE0101U1",  # people per km²
                "BE0101U2",  # population
                "BE0101U3",  # land area in km²
            ],
            "Tid": [YEAR],
        },
    ),
}


# ---------- talking to SCB ----------


def _get(url, **kwargs):
    """Send a request to SCB. If SCB says "slow down" (429), wait and try again."""
    method = kwargs.pop("method", "GET")
    for attempt in range(5):  # max 5 tries
        response = requests.request(method, url, headers=HEADERS, timeout=60, **kwargs)
        if response.status_code == 429:  # too many calls (~30 per 10 s)
            print("Too many requests, waiting 10 s ...")
            time.sleep(10)
            continue
        if response.status_code >= 400:  # any other error – stop and show it
            raise RuntimeError(
                f"{response.status_code} from SCB: {response.text[:500]}"
            )
        return response.json()
    raise RuntimeError("SCB kept answering 429 – try again later")


def search_tables(query, lang="sv"):
    """Search SCB's tables by words, e.g. search_tables("folkmängd kommun")."""
    data = _get(f"{API}/tables", params={"query": query, "lang": lang, "pageSize": 30})
    for t in data.get("tables", []):  # one line per table: id, years, title
        print(
            f"{t['id']:<9} {t.get('firstPeriod', '')}–{t.get('lastPeriod', '')}  {t['label']}"
        )


def show_metadata(table_id, lang="sv", max_values=8):
    """Show what's inside a table (its columns and a few values)."""
    meta = _get(f"{API}/tables/{table_id}/metadata", params={"lang": lang})
    print(meta.get("label", table_id))
    for dim_id in meta["id"]:
        labels = meta["dimension"][dim_id]["category"]["label"]
        values = list(labels.items())
        print(f"\n{dim_id}  ({len(values)} values)")
        for code, label in values[:max_values]:  # only the first few
            print(f"   {code:<12} {label}")
        if len(values) > max_values:
            print("   ...")


def fetch_table(table_id, selection, lang="sv"):
    """Download the data from one table, in the JSON-stat2 format."""
    # turn my simple dict into the shape SCB wants
    body = {
        "selection": [
            {"variableCode": var, "valueCodes": codes}
            for var, codes in selection.items()
        ]
    }
    return _get(
        f"{API}/tables/{table_id}/data",
        method="POST",  # POST = "here's my order"
        params={"lang": lang, "outputFormat": "json-stat2"},
        json=body,
    )


# ---------- JSON-stat2 -> normal rows ----------


def jsonstat_to_rows(js):
    """Turn SCB's answer into normal rows (one per region x measure).

    SCB sends all numbers in one long list. The order follows the columns,
    like nested loops, so we loop the same way to know which number is which.
    """
    dims = js["id"]  # the column names, in order
    codes_per_dim = []
    for dim_id in dims:
        index = js["dimension"][dim_id]["category"]["index"]
        # the codes come either as {code: position} or as a list – handle both
        codes = sorted(index, key=index.get) if isinstance(index, dict) else list(index)
        codes_per_dim.append(codes)

    values = js["value"]
    if isinstance(values, dict):  # only some values sent? fill the gaps with None
        values = [values.get(str(i)) for i in range(_cube_size(codes_per_dim))]

    rows = []
    # product() makes every combination, in the same order as the numbers
    for position, combo in enumerate(product(*codes_per_dim)):
        row = {}
        for dim_id, code in zip(dims, combo):
            label = js["dimension"][dim_id]["category"].get("label", {}).get(code, code)
            row[dim_id] = code  # e.g. 0114
            row[f"{dim_id}_label"] = label  # e.g. Upplands Väsby
        row["value"] = values[position]
        rows.append(row)
    return rows


def _cube_size(codes_per_dim):
    """How many numbers there should be in total (e.g. 312 x 3 = 936)."""
    size = 1
    for codes in codes_per_dim:
        size *= len(codes)
    return size


# ---------- save and load ----------
# The JSON files are always read and written as UTF-8,
# otherwise Windows breaks names like "Österåker".


def download_all():
    """Download every table in TABLES and save SCB's answer as a JSON file."""
    if not TABLES:
        raise RuntimeError("TABLES is empty – fill it in first (see notebook 03).")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, (table_id, selection) in TABLES.items():
        path = RAW_DIR / f"scb_{name}_{table_id}_{date.today()}.json"
        if path.exists():  # already got it today – skip the API call
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
    """Put each saved table into DuckDB as raw.scb_<name>."""
    con = duckdb.connect(str(DB_PATH))
    con.sql("CREATE SCHEMA IF NOT EXISTS raw")
    for name, (table_id, path) in paths.items():
        rows = jsonstat_to_rows(json.loads(path.read_text(encoding="utf-8")))
        df = pd.DataFrame(
            rows
        )  # rows -> table (codes stay as text, so 0114 keeps its 0)
        df["_table_id"] = table_id  # which SCB table
        df["_source"] = path.name  # which file
        # DuckDB can read the DataFrame just by its name, df
        con.sql(f"""
            CREATE OR REPLACE TABLE raw.scb_{name} AS
            SELECT *, current_timestamp AS _loaded_at
            FROM df
        """)
        print(f"raw.scb_{name}: {len(df)} rows")
    con.close()


if __name__ == "__main__":  # only runs when you start this file directly
    load_all(download_all())
