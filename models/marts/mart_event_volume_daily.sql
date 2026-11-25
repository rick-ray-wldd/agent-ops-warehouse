-- Events per UTC day on the calendar spine, with a trailing 7-day average (the day and the 6 before it).
with daily as (
    select d.date_day, count(e.event_id) as events
    from {{ ref('dim_date') }} d
    left join {{ ref('fct_event') }} e on e.date_key = d.date_key
    group by 1
)
select
    date_day,
    events,
    round(avg(events) over (order by date_day rows between 6 preceding and current row), 3) as rolling_7d_avg
from daily
