-- Every cell centre must lie within Sweden's rough box in SWEREF 99 TM (meters).
-- Catches wrong coordinate systems or swapped x/y.
select cell_id, ST_X(centroid) as x, ST_Y(centroid) as y
from {{ ref('stg_scb__grid_1km') }}
where ST_X(centroid) not between 200000 and 1000000
   or ST_Y(centroid) not between 6100000 and 7700000