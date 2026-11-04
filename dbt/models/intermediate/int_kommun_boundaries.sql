-- One polygon per municipality, made by merging its DeSO areas.
-- A table (not a view) because merging ~6 000 polygons takes a moment.

select
    kommun_code,
    any_value(lan_code)             as lan_code,
    count(*)                        as deso_areas,
    ST_Union_Agg(geom)              as geom
from {{ ref('stg_scb__deso') }}
group by kommun_code
