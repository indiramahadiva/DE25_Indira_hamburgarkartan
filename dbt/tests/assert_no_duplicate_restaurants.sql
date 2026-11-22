-- No restaurant may be in the data twice: two rows of the same chain,
-- from different sources (node / way / manual), within 100 m of each other
-- are the same restaurant. Also catches a manual addition that already exists in OSM.
select
    a.restaurant_id,
    b.restaurant_id                        as duplicate_of,
    a.chain,
    round(ST_Distance(a.geom, b.geom))     as meters
from {{ ref('stg_osm__restaurants') }} a
join {{ ref('stg_osm__restaurants') }} b
  on a.chain = b.chain
 and a.osm_type != b.osm_type
 and a.restaurant_id < b.restaurant_id
 and ST_DWithin(a.geom, b.geom, 100)
