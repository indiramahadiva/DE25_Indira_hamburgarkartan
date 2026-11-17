-- One row per populated 1 km cell: population, municipality and distances.
-- Answers F1 (distance), F2 (deserts) and F4 (nearest chain) at the finest level.
--
-- The municipality is found with point-in-polygon on the cell centre.
-- Cells on the coast can have their centre in the sea, outside every
-- municipality polygon; they get the nearest municipality instead.

with cells as (

    select cell_id, population, centroid
    from {{ ref('stg_scb__grid_1km') }}

),

distances as (

    select * from {{ ref('int_grid_nearest_restaurant') }}

),

kommuner as (

    select kommun_code, geom from {{ ref('dim_kommun') }}

),

inside as (

    select c.cell_id, k.kommun_code, 'inside' as kommun_match
    from cells c
    join kommuner k on ST_Contains(k.geom, c.centroid)

),

nearest as (

    select c.cell_id, k.kommun_code, 'nearest' as kommun_match
    from cells c
    cross join kommuner k
    where c.cell_id not in (select cell_id from inside)
    qualify row_number() over (
        partition by c.cell_id order by ST_Distance(c.centroid, k.geom)
    ) = 1

),

placed as (

    select * from inside
    union all
    select * from nearest

)

select
    c.cell_id,
    p.kommun_code,
    p.kommun_match,
    c.population,
    d.dist_any_m,
    d.dist_mcdonalds_m,
    d.dist_max_m,
    d.dist_burger_king_m,
    d.dist_sibylla_m,
    d.nearest_chain,
    d.nearest_restaurant_id,
    c.centroid
from cells c
join placed p using (cell_id)
join distances d using (cell_id)
