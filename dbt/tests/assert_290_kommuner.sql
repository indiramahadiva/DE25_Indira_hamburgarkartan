-- Sweden has 290 municipalities. Returns a row (= test fails) if the count differs.
select count(*) as municipalities
from {{ ref('stg_scb__kommun_stats') }}
having count(*) != 290