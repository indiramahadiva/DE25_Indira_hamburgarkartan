-- The distance to "any chain" must equal the shortest of the four chain distances.
select cell_id, dist_any_m
from {{ ref('int_grid_nearest_restaurant') }}
where abs(dist_any_m - least(dist_mcdonalds_m, dist_max_m, dist_burger_king_m, dist_sibylla_m)) > 0.001
