-- Every populated cell must appear exactly once in the fact table.
select
    (select count(*) from {{ ref('stg_scb__grid_1km') }})     as cells,
    (select count(*) from {{ ref('fct_grid_accessibility') }}) as cells_in_fact
where (select count(*) from {{ ref('stg_scb__grid_1km') }})
   != (select count(*) from {{ ref('fct_grid_accessibility') }})
