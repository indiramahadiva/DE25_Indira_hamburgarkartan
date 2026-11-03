-- One row per chain (4 rows). Comes straight from the seed.

select
    chain,
    chain_name,
    brand_wikidata,
    origin
from {{ ref('chains') }}
