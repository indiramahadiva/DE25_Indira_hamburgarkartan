-- Every populated cell must get a distance – none may be lost.
select
    (select count(*) from {{ ref('stg_scb__grid_1km') }})           as cells,
    (select count(*) from {{ ref('int_grid_nearest_restaurant') }}) as cells_with_distance
where (select count(*) from {{ ref('stg_scb__grid_1km') }})
   != (select count(*) from {{ ref('int_grid_nearest_restaurant') }})
