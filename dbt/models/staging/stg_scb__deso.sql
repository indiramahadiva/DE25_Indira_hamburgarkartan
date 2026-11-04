-- One row per DeSO area (SCB 2025). Only used as building blocks for
-- municipality borders – the analysis itself stops at municipality level.

with source as (

    select * from {{ source('raw', 'scb_deso') }}

)

select
    desokod                         as deso_code,
    kommunkod                       as kommun_code,
    lanskod                         as lan_code,
    regsokod                        as regso_code,
    ST_MakeValid(sp_geometry)       as geom             -- repairs small drawing errors
from source
