-- No two restaurants of the same chain may lie within 100 m of each other.
-- If they do, the same restaurant is probably mapped twice in OpenStreetMap.
select a.restaurant_id, b.restaurant_id as duplicate_of, a.chain,
       round(ST_Distance(a.geom, b.geom)) as meters
from {{ ref('stg_osm__restaurants') }} a
join {{ ref('stg_osm__restaurants') }} b
  on a.chain = b.chain
 and a.restaurant_id < b.restaurant_id
 and ST_DWithin(a.geom, b.geom, 100)