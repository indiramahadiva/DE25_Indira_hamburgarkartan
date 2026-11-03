-- No municipality may be lost when statistics and borders are joined.
select count(*) as municipalities
from {{ ref('dim_kommun') }}
having count(*) != 290
