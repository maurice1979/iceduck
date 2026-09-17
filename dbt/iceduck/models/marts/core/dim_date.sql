{{ config(materialized='external', location='target/gold/' ~ this.identifier ~ '.parquet', format='parquet') }}

with all_dates as (
    select cast(started_at as date) as d from {{ iceberg_source('silver', 'stg_encounters') }}
    union all
    select cast(stopped_at as date) from {{ iceberg_source('silver', 'stg_encounters') }}
    union all
    select cast(started_at as date) from {{ iceberg_source('silver', 'stg_medications') }}
    union all
    select cast(stopped_at as date) from {{ iceberg_source('silver', 'stg_medications') }}
    union all
    select started_on from {{ iceberg_source('silver', 'stg_conditions') }}
    union all
    select stopped_on from {{ iceberg_source('silver', 'stg_conditions') }}
),

bounds as (
    select min(d) as min_date, max(d) as max_date
    from all_dates
    where d is not null
),

spine as (
    select unnest(generate_series(
        (select min_date from bounds),
        (select max_date from bounds),
        interval 1 day
    ))::date as date_day
)

select
    date_day,
    extract(year from date_day) as year,
    extract(quarter from date_day) as quarter,
    extract(month from date_day) as month,
    strftime(date_day, '%B') as month_name,
    extract(day from date_day) as day_of_month,
    dayofweek(date_day) as day_of_week,
    strftime(date_day, '%A') as day_name,
    dayofweek(date_day) in (0, 6) as is_weekend
from spine
