-- One row per municipality: population, land area and density for 2025.
-- Source is long format (one row per region x measure), so we pivot here.

with source as (

    select * from {{ source('raw', 'scb_kommun_stats') }}

),

municipalities as (

    select *
    from source
    where length(Region) = 4          -- 4-digit codes = municipalities (00 = Sweden, 2 digits = county)

)

select
    Region                                                          as kommun_code,
    Region_label                                                    as kommun_name,
    left(Region, 2)                                                 as lan_code,
    cast(Tid as integer)                                            as year,
    cast(max(value) filter (where ContentsCode = 'BE0101U2') as integer) as population,
    max(value) filter (where ContentsCode = 'BE0101U3')            as land_area_km2,
    max(value) filter (where ContentsCode = 'BE0101U1')            as people_per_km2
from municipalities
group by Region, Region_label, Tid