-- One row per restaurant, placed in the municipality it lies in.
-- A few restaurants on the coast or a pier can fall just outside every
-- municipality polygon; they get the nearest municipality instead.

with restaurants as (

    select * from {{ ref('stg_osm__restaurants') }}

),

kommuner as (

    select kommun_code, geom from {{ ref('dim_kommun') }}

),

inside as (

    -- normal case: the point lies inside a municipality
    select r.restaurant_id, k.kommun_code, 'inside' as kommun_match
    from restaurants r
    join kommuner k on ST_Contains(k.geom, r.geom)

),

nearest as (

    -- fallback: points outside every polygon -> closest municipality
    select r.restaurant_id, k.kommun_code, 'nearest' as kommun_match
    from restaurants r
    cross join kommuner k
    where r.restaurant_id not in (select restaurant_id from inside)
    qualify row_number() over (
        partition by r.restaurant_id order by ST_Distance(r.geom, k.geom)
    ) = 1

),

placed as (

    select * from inside
    union all
    select * from nearest

)

select
    r.restaurant_id,
    r.chain,
    p.kommun_code,
    p.kommun_match,
    r.name,
    r.osm_type,
    r.matched_by,
    r.geom
from restaurants r
join placed p using (restaurant_id)
