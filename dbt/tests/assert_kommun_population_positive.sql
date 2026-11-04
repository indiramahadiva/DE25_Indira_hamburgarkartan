-- Every municipality must have people and land. Returns the rows that break the rule.
select kommun_code, kommun_name, population, land_area_km2
from {{ ref('stg_scb__kommun_stats') }}
where population <= 0 or land_area_km2 <= 0