-- Summing per municipality must not lose or double-count anyone:
-- the municipality totals must add up to the cell totals.
select
    (select sum(population)      from {{ ref('fct_grid_accessibility') }})   as cell_total,
    (select sum(grid_population) from {{ ref('fct_kommun_accessibility') }}) as kommun_total
where (select sum(population)      from {{ ref('fct_grid_accessibility') }})
   != (select sum(grid_population) from {{ ref('fct_kommun_accessibility') }})
