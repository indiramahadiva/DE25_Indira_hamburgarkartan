-- The first four characters of a DeSO code are its municipality code.
-- If not, the DeSO -> municipality merge would be wrong.
select deso_code, kommun_code
from {{ ref('stg_scb__deso') }}
where left(deso_code, 4) != kommun_code