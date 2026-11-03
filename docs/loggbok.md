# Logbook – Hamburgarkartan

What I did, what broke, and how I fixed it.

**Entry format:** **Done** · **Problem → Fix** · **Decision** · **Commits**

Last updated: 2026-11-03 (week 45)

---

## Timeline

| Week  | Date      | Phase                                     | Status         |
| ----- | --------- | ----------------------------------------- | -------------- |
| 38–40 | Sep       | Planning: topic, project choice, schedule | ✅             |
| 40–41 | Oct 2–5   | Setup: repo, Python, DuckDB               | ✅             |
| 41    | Oct 5     | Supervision 1                             | ✅             |
| 43–44 | Oct 22–26 | Ingestion: four data sources              | ✅             |
| 44–45 | Oct 27 –  | Data modeling + dbt                       | 🔄 in progress |
| 45    |           | Supervision 2                             | 📋             |
| 45–47 |           | Distance calculation                      | 📋             |
| 47–50 |           | Dagster + Streamlit dashboard             | 📋             |

---

## Phase 1 – Planning (weeks 38–40)

**Done**

- Picked a topic. Requirements: open data (no login, no scraping), enough volume for a real pipeline, and something I actually care about.
- Also considered an aurora-chance data warehouse (Norrskenskollen), but went with the burger map.
- Wrote the project choice, project plan and Gantt schedule using the course templates. Submitted before the Sep 30 deadline.

**Problem → Fix**

- _Scope could get too big._ → Limited to four chains (McDonald's, Max, Burger King, Sibylla), Sweden only, straight-line distance. Income correlation became a stretch goal.
- _DeSO (~6,000 areas) added a source without adding answers._ → Dropped as an analysis level; the 1 km grid is already finer.

---

## Phase 2 – Setup (Oct 2–5)

**Done**

- GitHub repo + Python project with `uv` (Python 3.13, pinned in `uv.lock`).
- Folders for raw data (`data/raw/`) and the database (`warehouse/`), not tracked in git.
- Smoke test `scripts/check_duckdb.py`: Stockholm–Uppsala distance calculated two ways.

**Problem → Fix**

- _Distances between GPS coordinates come out in degrees, not meters._ → Everything gets transformed to **SWEREF 99 TM (EPSG:3006)**, Sweden's meter-based CRS. The smoke test shows the difference.
- _Lat/lon can get flipped during transform._ → Always use `always_xy := true`.

**Commits**
[`e4ef9ce`](https://github.com/indiramahadiva/DE25_Indira_hamburgarkartan/commit/e4ef9ce) Initialize Python project with uv ·
[`3fa7fc0`](https://github.com/indiramahadiva/DE25_Indira_hamburgarkartan/commit/3fa7fc0) Add project structure and DuckDB spatial test

### Oct 5 – Supervision 1

- Went through the project choice, incl. whether the data volume is enough.
- _TODO: add supervisor feedback._

---

## Phase 3 – Ingestion (Oct 22–26)

### Oct 22 – OpenStreetMap, first version

**Done**

- `geofabrik.py` downloads Sweden's OSM data and pulls out all fast food places and restaurants.

**Problem → Fix**

- _Overpass API (from the project plan) was flaky when testing._ → Switched to downloading the full Sweden file from **Geofabrik** (943 MB) and reading it with DuckDB. More reliable, and the same file always gives the same result. _Deviation from plan._
- _Some restaurants are drawn as buildings_ (OSM "ways") with no single coordinate. → The script computes the building's center from its corners.
- _After renaming the package to `hamburgarkartan`, it wouldn't install on a fresh machine._ → Added `module-name` in `pyproject.toml`.

**Commits**
[`7699e03`](https://github.com/indiramahadiva/DE25_Indira_hamburgarkartan/commit/7699e03) Add Geofabrik OSM download for ingestion ·
[`6afa633`](https://github.com/indiramahadiva/DE25_Indira_hamburgarkartan/commit/6afa633) Fix package name in pyproject after rename

### Oct 26 – OpenStreetMap, faster + explored

**Done**

- Rewrote the read. Runtime: **28 s**, **15,483** food places in Sweden.
- Notebook `01_explore_osm.ipynb` to check how the chains are tagged.

**Problem → Fix**

- _First version was so slow I had to kill it._ It kept every point in Sweden in memory to find building corners. → Two light passes: first just the food places, then only the corners needed.
- _How do you know a place is really a McDonald's?_ Names are spelled all kinds of ways. → Each chain has a fixed **Wikidata ID** (McDonald's Q38076, Max Q1912172, Burger King Q177054, Sibylla Q488643). **95 %** of places have it; the rest are matched by name.
- _Chains without `amenity=fast_food/restaurant` got dropped._ → Also keep places with a chain's `brand`, whatever the tag. +5 places.
- _False matches:_ a clothing store called Max, two "Max Falafel", and two Max restaurants not open yet. → Raw data stays untouched. Cleaned in dbt with an exclusion list and an "opens" filter.

**Commits**
[`a319109`](https://github.com/indiramahadiva/DE25_Indira_hamburgarkartan/commit/a319109) Speed up OSM extraction with two-pass read ·
[`8072b9e`](https://github.com/indiramahadiva/DE25_Indira_hamburgarkartan/commit/8072b9e) /
[`f6debee`](https://github.com/indiramahadiva/DE25_Indira_hamburgarkartan/commit/f6debee) OSM exploration notebook with findings

### Oct 26 – SCB population grid

**Done**

- `scb_grid.py` fetches population per 1 km cell for **2025** from SCB's map service (WFS). **115,118** cells.
- Notebook `02_explore_scb_grid.ipynb`.

**Problem → Fix**

- _A map service can return an error message instead of data._ → Script checks the file really is a GeoPackage before saving.
- _Plan said 200,000+ cells, got 115,118._ → SCB only publishes cells where people live. Doesn't affect the analysis, but it's a _deviation from plan_. Distance calc is still ~70 million pairs.

**Decision**

- Year **2025**: latest available and closest to the OSM file (Oct 2026).
- Grid already comes in SWEREF 99 TM, so no transform needed.

**Commits**
[`a050411`](https://github.com/indiramahadiva/DE25_Indira_hamburgarkartan/commit/a050411) Add SCB population grid ingestion ·
[`38efe57`](https://github.com/indiramahadiva/DE25_Indira_hamburgarkartan/commit/38efe57) Add SCB grid exploration notebook

### Oct 26 – SCB municipality stats (API)

**Done**

- `scb_pxweb.py` against SCB's new **PxWebApi v2**. Gets table **TAB628** (population, land area, density per region, 2025). **936** values = 290 municipalities + counties + national, × 3 measures.
- Notebook `03_explore_kommun_stats.ipynb`.

**Problem → Fix**

- _SCB has thousands of tables._ → Wrote helpers (`search_tables`, `show_metadata`) to find the right one. One table had everything.
- _SCB rate-limits (~30 calls / 10 s)._ → Script waits and retries.
- _Database file was locked:_ an open notebook held the connection (on Windows even a read connection blocks). → Close the notebook connection before running scripts.
- _Å, ä, ö got mangled:_ Windows saves text as cp1252, not what DuckDB expects. → Always read/write **UTF-8**.

**Commits**
[`c09e194`](https://github.com/indiramahadiva/DE25_Indira_hamburgarkartan/commit/c09e194) Add SCB PxWeb municipality ingestion

### Oct 26 – Municipality boundaries

**Done**

- `boundaries.py` + notebook `04_explore_boundaries.ipynb`. **6,160** DeSO areas.

**Problem → Fix**

- _SCB's map service has no municipality boundary layer._ → Every DeSO sits in exactly one municipality, and the first four chars of the DeSO code are the municipality code. Merging DeSOs by code gives the boundaries — same source, year and CRS as the grid. DeSO is just a building block; analysis stays at municipality level.

**Commits**
[`18a8cff`](https://github.com/indiramahadiva/DE25_Indira_hamburgarkartan/commit/18a8cff) Add municipality boundaries ingestion via DeSO

### Oct 26 – Ingestion done

All four sources loaded and checked. Merged into `main` via PR.

| Source                               | Raw table              | Rows    |
| ------------------------------------ | ---------------------- | ------- |
| OpenStreetMap (Geofabrik 2026-10-26) | `raw.osm_food_places`  | 15,483  |
| SCB 1 km grid, 2025                  | `raw.scb_grid_1km`     | 115,118 |
| SCB TAB628, 2025                     | `raw.scb_kommun_stats` | 936     |
| SCB DeSO 2025                        | `raw.scb_deso`         | 6,160   |

**Commits**
[`3a29b8e`](https://github.com/indiramahadiva/DE25_Indira_hamburgarkartan/commit/3a29b8e) Merge pull request #1 (feature/ingestion)

---

## Phase 4 – Data modeling + dbt (Oct 27 –)

### Oct 27 – Data model

**Done**

- Designed a **star schema**: three dims (`dim_chain`, `dim_kommun`, `dim_restaurant`) and two facts (`fct_grid_accessibility` per cell, `fct_kommun_accessibility` per municipality). Each table answers one or more of Q1–Q4. See [datamodell.md](datamodell.md).

**Decision**

- Layers: raw → staging → intermediate → marts. Raw is never changed; all cleaning happens in dbt.
- "Burger desert" threshold not decided yet, so keeping three levels (10, 20, 50 km) — bring up at supervision 2.
- Chain list and false matches go in small CSVs (dbt seeds) so the rules are visible and easy to change.

### Oct 27 – dbt project

**Done**

- Set up dbt with DuckDB. First model `stg_scb__kommun_stats` turns SCB's long format into one row per municipality.
- **8 tests green**, e.g. "exactly 290 municipalities" and "population > 0".

**Problem → Fix**

- _dbt names the schema `main_staging` by default._ → Small macro (`generate_schema_name`) gives clean names: `staging`, `intermediate`, `marts`.
- _`profiles.yml` normally lives in the home folder._ → Kept it in the repo so supervisor and opponent can run everything right after `git clone`.

**Commits**
[`0de6177`](https://github.com/indiramahadiva/DE25_Indira_hamburgarkartan/commit/0de6177) Set up dbt project with first staging model and tests

### In progress (week 45)

- Staging for the grid and DeSO, boundaries as one polygon per municipality, and four new tests (incl. grid population matches SCB's official figure within 1 %).
- Then restaurants with the matching rule and the two seeds.

---

## Summary: problems + fixes

| #   | Problem                                               | Fix                                        |
| --- | ----------------------------------------------------- | ------------------------------------------ |
| 1   | Distances in degrees, not meters                      | Everything in SWEREF 99 TM (EPSG:3006)     |
| 2   | Overpass API flaky                                    | Geofabrik file instead                     |
| 3   | Restaurants drawn as buildings have no coordinate     | Center of the building's corners           |
| 4   | Package wouldn't install after rename                 | `module-name` in `pyproject.toml`          |
| 5   | OSM read too slow                                     | Two light passes – 28 s                    |
| 6   | Chain names spelled differently                       | Wikidata ID (95 %), name as fallback       |
| 7   | Chains without the right `amenity` tag dropped        | Also keep chains' `brand`                  |
| 8   | False matches (clothing store, Max Falafel, not open) | Exclusion list + "opens" filter in dbt     |
| 9   | Map service can return errors instead of data         | Check file is a GeoPackage                 |
| 10  | Fewer cells than planned                              | Logged as deviation; no effect on analysis |
| 11  | Hard to find the right SCB table                      | Own search helpers; one table was enough   |
| 12  | SCB rate limits                                       | Wait and retry                             |
| 13  | DB file locked by notebook (Windows)                  | Close connection before running scripts    |
| 14  | Å, ä, ö broken (Windows)                              | Always UTF-8                               |
| 15  | No municipality boundaries at SCB                     | Built from DeSO areas                      |
| 16  | dbt schema names                                      | Custom schema-name macro                   |

## Deviations from the plan

| Plan                              | Reality         | Why                                                        |
| --------------------------------- | --------------- | ---------------------------------------------------------- |
| Overpass API                      | Geofabrik file  | Overpass flaky                                             |
| 200,000+ cells                    | 115,118         | SCB only publishes populated cells                         |
| Boundaries from a separate source | Built from DeSO | No municipality map at SCB                                 |
| Ingestion weeks 41–43             | Done week 44    | Data messier than expected (false matches, Windows issues) |

## Lessons learned

- **Explore the data before using it.** The notebooks caught the problems (wrong chains, fewer cells) before they hit the analysis.
- **A fixed ID beats names.** "Max" is a common word; the Wikidata ID separates the burger chain from the clothing store.
- **Never touch raw data.** Then you can always trace why a row was removed.

## Next steps

1. Build + test staging for grid and DeSO, plus the boundaries.
2. `stg_osm__restaurants` with the matching rule and seeds.
3. Dimension tables.
4. Distance calculation (activity 6).
5. Dagster + Streamlit.
