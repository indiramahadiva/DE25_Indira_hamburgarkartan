-- More people live beyond 10 km than beyond 20 km, and beyond 20 than 50.
-- None of these can be larger than the municipality's population in the grid.
select kommun_code, grid_population, pop_beyond_10km, pop_beyond_20km, pop_beyond_50km
from {{ ref('fct_kommun_accessibility') }}
where not (pop_beyond_50km <= pop_beyond_20km
       and pop_beyond_20km <= pop_beyond_10km
       and pop_beyond_10km <= grid_population)
