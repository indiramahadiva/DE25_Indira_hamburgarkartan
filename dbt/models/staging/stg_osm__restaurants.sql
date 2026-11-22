-- One row per open restaurant of the four chains, as a point in SWEREF 99 TM.
-- Matching rule (see docs/datamodell.md and notebook 01):
--   1. match on brand:wikidata
--   2. no wikidata id -> match on brand/name, but not if it is a shop
--   3. drop places that are not open yet ("opens ..." in the name)
--   4. drop places in the manual exclusion list (seed)
--   5. drop duplicates: the same restaurant mapped twice in OSM
--      (e.g. as a point AND as the building) – same chain within 100 m

with source as (

    select * from {{ source('raw', 'osm_food_places') }}

),

chains as (

    select * from {{ ref('chains') }}

),

exclusions as (

    select * from {{ ref('osm_manual_exclusions') }}

),

prepared as (

    select
        osm_type,
        osm_id,
        lat,
        lon,
        tags['name']                                     as name,
        tags['brand:wikidata']                           as brand_wikidata,
        tags['shop']                                     as shop,
        lower(tags['brand'])                             as brand_lower,
        lower(tags['name'])                              as name_lower,
        lower(coalesce(tags['brand'], tags['name']))     as brand_or_name
    from source

),

matched as (

    select
        p.*,
        c.chain                                          as chain_by_id,      -- rule 1
        case
            when p.brand_wikidata is null and p.shop is null then             -- rule 2
                case
                    when p.brand_or_name like '%mcdonald%'
                      or p.brand_or_name like '%mc donald%'  then 'mcdonalds'
                    when p.brand_or_name like '%burger king%' then 'burger_king'
                    when p.brand_or_name like '%sibylla%'     then 'sibylla'
                    when p.brand_lower in ('max', 'max burgers')
                      or p.name_lower  in ('max', 'max burgers')
                      or p.name_lower  like 'max %'          then 'max'
                end
        end                                              as chain_by_name
    from prepared p
    left join chains c on p.brand_wikidata = c.brand_wikidata

),

matched_and_filtered as (

    select
        osm_type || '/' || osm_id                            as restaurant_id,
        osm_type,
        osm_id,
        coalesce(chain_by_id, chain_by_name)                 as chain,
        case when chain_by_id is not null
             then 'wikidata' else 'name_fallback' end        as matched_by,
        name,
        ST_Transform(ST_Point(lon, lat), 'EPSG:4326', 'EPSG:3006', always_xy := true) as geom
    from matched m
    where coalesce(chain_by_id, chain_by_name) is not null
      and lat is not null
      and not coalesce(regexp_matches(name_lower, 'opens|öppnar|coming soon|kommer snart'), false)   -- rule 3
      and not exists (                                                                                 -- rule 4
            select 1 from exclusions e
            where e.osm_type = m.osm_type and e.osm_id = m.osm_id
      )

),

ranked as (

    -- which copy to keep: wikidata match first, then the point (node), then lowest id
    select
        *,
        case matched_by when 'wikidata' then 0 else 1 end as rank_match,
        case osm_type   when 'node'     then 0 else 1 end as rank_type
    from matched_and_filtered

)

select
    a.restaurant_id,
    a.osm_type,
    a.osm_id,
    a.chain,
    a.matched_by,
    a.name,
    a.geom
from ranked a
where not exists (                                                                                 -- rule 5
    select 1
    from ranked b
    where b.chain = a.chain
      and b.restaurant_id != a.restaurant_id
      and ST_DWithin(a.geom, b.geom, 100)
      and (
            b.rank_match < a.rank_match
         or (b.rank_match = a.rank_match and b.rank_type < a.rank_type)
         or (b.rank_match = a.rank_match and b.rank_type = a.rank_type and b.restaurant_id < a.restaurant_id)
      )
)