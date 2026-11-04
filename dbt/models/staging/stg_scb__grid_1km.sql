-- One row per populated 1 km grid cell (SCB 2025), in SWEREF 99 TM (EPSG:3006).
-- The cell centre is where we measure distances from.

with source as (

    select * from {{ source('raw', 'scb_grid_1km') }}

)

select
    rutid_scb                       as cell_id,
    rutid_inspire                   as cell_id_inspire,
    rutstorl                        as cell_size_m,
    beftotalt                       as population,
    referenstid                     as reference_date,
    sp_geometry                     as geom,            -- the 1 x 1 km square
    ST_Centroid(sp_geometry)        as centroid         -- its middle point
from source
where beftotalt > 0                 -- only cells where people live
