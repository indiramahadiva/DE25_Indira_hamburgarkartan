-- One row per open restaurant of the four chains, as a point in SWEREF 99 TM.
-- Matching rule (see docs/datamodell.md and notebook 01):
--   1. match on brand:wikidata
--   2. no wikidata id -> match on brand/name, but not if it is a shop
--   3. drop places that are not open yet ("opens ..." in the name)
--   4. drop places in the manual exclusion list (seed)

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

)

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
