-- A calendar spine over the whole event range, so a day with no events still shows up as zero.
with bounds as (
    select cast(min(event_time_utc) as date) as first_day, cast(max(event_time_utc) as date) as last_day
    from {{ ref('stg_events') }}
),
days as (
    select cast(unnest(generate_series(first_day, last_day, interval 1 day)) as date) as date_day
    from bounds
)
select
    date_day,
    cast(strftime(date_day, '%Y%m%d') as integer) as date_key,
    dayofweek(date_day)                           as day_of_week,
    dayofweek(date_day) in (0, 6)                 as is_weekend,
    cast(date_trunc('week', date_day) as date)    as week_start
from days
