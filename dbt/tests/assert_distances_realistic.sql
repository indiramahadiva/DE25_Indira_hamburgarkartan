-- Distances must be between 0 and 500 km. Sweden is ~1 600 km long, but no
-- populated cell is that far from every restaurant. Values outside this range
-- mean a coordinate-system error (e.g. degrees instead of meters).
select cell_id, dist_any_m
from {{ ref('int_grid_nearest_restaurant') }}
where dist_any_m < 0 or dist_any_m > 500000
