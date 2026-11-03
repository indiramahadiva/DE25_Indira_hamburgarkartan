-- The grid total should be close to SCB's official population (TAB628).
-- SCB adjusts small grid numbers for privacy, so we allow 1 % difference.
with grid as (
    select sum(population) as grid_total from {{ ref('stg_scb__grid_1km') }}
),
official as (
    select sum(population) as official_total from {{ ref('stg_scb__kommun_stats') }}
)
select grid_total, official_total,
       round(100.0 * (grid_total - official_total) / official_total, 2) as diff_pct
from grid, official
where abs(grid_total - official_total) > 0.01 * official_total