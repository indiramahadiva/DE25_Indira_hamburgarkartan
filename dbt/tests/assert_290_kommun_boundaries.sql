-- One merged polygon per municipality: exactly 290.
select count(*) as municipalities
from {{ ref('int_kommun_boundaries') }}
having count(*) != 290