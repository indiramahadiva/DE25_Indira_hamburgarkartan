-- Every restaurant from staging must end up in dim_restaurant exactly once.
select
    (select count(*) from {{ ref('stg_osm__restaurants') }}) as in_staging,
    (select count(*) from {{ ref('dim_restaurant') }})       as in_dim
where (select count(*) from {{ ref('stg_osm__restaurants') }})
   != (select count(*) from {{ ref('dim_restaurant') }})
