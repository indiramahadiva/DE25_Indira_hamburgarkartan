-- Every chain should have a realistic number of restaurants in Sweden.
-- Fewer than 50 means the matching rule has broken for that chain.
select c.chain, count(r.restaurant_id) as restaurants
from {{ ref('chains') }} c
left join {{ ref('stg_osm__restaurants') }} r using (chain)
group by c.chain
having count(r.restaurant_id) < 50
