-- For every populated 1 km cell: distance to the nearest restaurant,
-- overall and per chain (method A: compare every cell with every restaurant).
--
-- ~115 000 cells x ~600 restaurants = ~70 million distance pairs.
-- All geometries are in SWEREF 99 TM (meters), so the straight-line distance
-- is plain Pythagoras on x/y – the same result as ST_Distance, but much
-- faster because it works on numbers instead of geometry objects.

with cells as (

    select
        cell_id,
        ST_X(centroid) as x,
        ST_Y(centroid) as y
    from {{ ref('stg_scb__grid_1km') }}

),

restaurants as (

    select
        restaurant_id,
        chain,
        ST_X(geom) as x,
        ST_Y(geom) as y
    from {{ ref('dim_restaurant') }}

),

pairs as (

    -- every cell against every restaurant
    select
        c.cell_id,
        r.restaurant_id,
        r.chain,
        sqrt(power(c.x - r.x, 2) + power(c.y - r.y, 2)) as dist_m
    from cells c
    cross join restaurants r

)

select
    cell_id,
    min(dist_m)                                          as dist_any_m,
    min(dist_m) filter (where chain = 'mcdonalds')       as dist_mcdonalds_m,
    min(dist_m) filter (where chain = 'max')             as dist_max_m,
    min(dist_m) filter (where chain = 'burger_king')     as dist_burger_king_m,
    min(dist_m) filter (where chain = 'sibylla')         as dist_sibylla_m,
    arg_min(chain, dist_m)                               as nearest_chain,
    arg_min(restaurant_id, dist_m)                       as nearest_restaurant_id
from pairs
group by cell_id
