import duckdb

# Bring in DuckDB, your local analytics database. No server needed.

con = duckdb.connect("warehouse/hamburgarkartan.duckdb")
# Open (or create) the database file in your warehouse folder.
# Everything you run goes through this "con" connection.

con.install_extension("spatial")
# Download the spatial extension. It only actually downloads the first time;
# later runs just see it's already there. Harmless to keep.

con.load_extension("spatial")
# Switch it on for this session. Without this, ST_Point etc. don't exist.

# Stockholm C and Uppsala C, as (lon, lat) in WGS84
# Note the order: longitude first, latitude second (x, y).

result = con.sql("""
    SELECT
        ST_Distance(
            ST_Point(18.0583, 59.3303),   -- Stockholm C as a point
            ST_Point(17.6464, 59.8586)    -- Uppsala C as a point
        ) AS distance_degrees,
        -- Straight-line distance... in DEGREES. Mathematically correct,
        -- practically useless. This is the "wrong way" for comparison.

        ST_Distance(
            ST_Transform(ST_Point(18.0583, 59.3303), 'EPSG:4326', 'EPSG:3006', always_xy := true),
            ST_Transform(ST_Point(17.6464, 59.8586), 'EPSG:4326', 'EPSG:3006', always_xy := true)
        ) / 1000 AS distance_km
        -- Convert both points from GPS coordinates (EPSG:4326) to
        -- SWEREF 99 TM (EPSG:3006), Sweden's official grid in METERS,
        -- then measure. Divide by 1000 to get km. This is the "right way".
""")
# Run the query. It's lazy, so nothing is fetched until you use it.

print(result)
# Show the result as a nice little table in the terminal.
