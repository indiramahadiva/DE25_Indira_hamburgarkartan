-- Every restaurant must lie within Sweden's rough box in SWEREF 99 TM (meters).
-- Catches swapped lat/lon in the transform.
select restaurant_id, ST_X(geom) as x, ST_Y(geom) as y
from {{ ref('stg_osm__restaurants') }}
where ST_X(geom) not between 200000 and 1000000
   or ST_Y(geom) not between 6100000 and 7700000
