-- One row per municipality in the summary table: exactly 290.
select count(*) as municipalities
from {{ ref('fct_kommun_accessibility') }}
having count(*) != 290
