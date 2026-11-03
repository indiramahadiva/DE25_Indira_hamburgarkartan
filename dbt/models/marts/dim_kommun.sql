-- One row per municipality (290 rows): statistics from SCB + border from DeSO.

select
    s.kommun_code,
    s.kommun_name,
    s.lan_code,
    s.population,
    s.land_area_km2,
    s.people_per_km2,
    b.deso_areas,
    b.geom
from {{ ref('stg_scb__kommun_stats') }} s
join {{ ref('int_kommun_boundaries') }} b using (kommun_code)
