-- One row per open restaurant of the four chains, as a point in SWEREF 99 TM.
-- Matching rule (see docs/datamodell.md and notebook 01):
--   1. match on brand:wikidata
--   2. no wikidata id -> match on brand/name, but not if it is a shop
--   3. drop places that are not open yet ("opens ..." in the name)
--   4. drop places in the manual exclusion list (seed)
--   5. add restaurants that are missing in OSM (seed, verified on Google Maps)
--   6. drop duplicates: the same restaurant mapped both as a point (node)
--      and as a building (way) within 100 m -> keep one

with source as (

    select * from {{ source('raw', 'osm_food_places') }}

),

chains as (

    select * from {{ ref('chains') }}

),

exclusions as (

    select * from {{ ref('osm_manual_exclusions') }}

),

additions as (

    select * from {{ ref('osm_manual_additions') }}

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

from_osm as (

    select
        osm_type || '/' || osm_id                        as restaurant_id,
        osm_type,
        osm_id,
        coalesce(chain_by_id, chain_by_name)             as chain,
        case when chain_by_id is not null
             then 'wikidata' else 'name_fallback' end    as matched_by,
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

duplicates as (

    -- rule 6: a node and a way of the same chain within 100 m are one restaurant.
    -- Keep the one matched on wikidata; if both are matched the same way, keep the node.
    select distinct b.restaurant_id
    from from_osm a
    join from_osm b
      on a.chain = b.chain
     and a.osm_type != b.osm_type
     and ST_DWithin(a.geom, b.geom, 100)
    where (a.matched_by = 'wikidata' and b.matched_by != 'wikidata')
       or (a.matched_by = b.matched_by and a.osm_type = 'node')

),

from_manual as (

    -- rule 5: restaurants missing in OSM, checked by hand on Google Maps
    select
        'manual/' || addition_id                         as restaurant_id,
        'manual'                                         as osm_type,
        cast(null as bigint)                             as osm_id,
        chain,
        'manual'                                         as matched_by,
        name,
        ST_Transform(ST_Point(lon, lat), 'EPSG:4326', 'EPSG:3006', always_xy := true) as geom
    from additions

)

select * from from_osm
where restaurant_id not in (select restaurant_id from duplicates)

union all

select * from from_manual
