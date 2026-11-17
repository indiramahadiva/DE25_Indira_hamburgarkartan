-- One row per municipality: the cells summed up. Answers F1–F4 per municipality.

with cells as (

    select * from {{ ref('fct_grid_accessibility') }}

),

kommuner as (

    select kommun_code, kommun_name, lan_code, population from {{ ref('dim_kommun') }}

),

restaurants as (

    select kommun_code, count(*) as restaurants
    from {{ ref('dim_restaurant') }}
    group by kommun_code

),

distance_summary as (

    select
        kommun_code,
        sum(population)                                              as grid_population,
        -- F1: average distance per person, not per cell
        sum(population * dist_any_m) / sum(population)               as pop_weighted_mean_dist_m,
        -- F2: people living far from any restaurant
        sum(population) filter (where dist_any_m > 10000)            as pop_beyond_10km,
        sum(population) filter (where dist_any_m > 20000)            as pop_beyond_20km,
        sum(population) filter (where dist_any_m > 50000)            as pop_beyond_50km
    from cells
    group by kommun_code

),

weighted_median as (

    -- the distance where half of the municipality's people live closer
    select kommun_code, min(dist_any_m) as median_dist_m
    from (
        select
            kommun_code,
            dist_any_m,
            sum(population) over (partition by kommun_code order by dist_any_m
                                  rows between unbounded preceding and current row) as cum_pop,
            sum(population) over (partition by kommun_code)                         as total_pop
        from cells
    )
    where cum_pop >= total_pop / 2.0
    group by kommun_code

),

chain_share as (

    -- F4: the chain that is nearest for the most people
    select kommun_code, arg_max(nearest_chain, people) as dominant_chain
    from (
        select kommun_code, nearest_chain, sum(population) as people
        from cells
        group by kommun_code, nearest_chain
    )
    group by kommun_code

)

select
    k.kommun_code,
    k.kommun_name,
    k.lan_code,
    k.population,
    d.grid_population,
    coalesce(r.restaurants, 0)                                       as restaurants,
    -- F3: restaurants per 10 000 inhabitants (official population)
    round(coalesce(r.restaurants, 0) * 10000.0 / k.population, 2)    as restaurants_per_10k,
    d.pop_weighted_mean_dist_m,
    m.median_dist_m,
    coalesce(d.pop_beyond_10km, 0)                                   as pop_beyond_10km,
    coalesce(d.pop_beyond_20km, 0)                                   as pop_beyond_20km,
    coalesce(d.pop_beyond_50km, 0)                                   as pop_beyond_50km,
    c.dominant_chain
from kommuner k
left join distance_summary d using (kommun_code)
left join weighted_median  m using (kommun_code)
left join chain_share      c using (kommun_code)
left join restaurants      r using (kommun_code)
