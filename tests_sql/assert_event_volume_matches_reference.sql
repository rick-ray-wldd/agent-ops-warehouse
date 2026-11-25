with expected as (
    select unnest(event_volume_daily, recursive := true) from read_json_auto('data/expected/metrics.json')
)
select e.day, e.events as expected_events, a.events as actual_events,
       e.rolling_7d_avg as expected_avg, a.rolling_7d_avg as actual_avg
from expected e
full join {{ ref('mart_event_volume_daily') }} a on a.date_day = cast(e.day as date)
where a.date_day is null or e.day is null
   or a.events <> e.events
   or abs(a.rolling_7d_avg - e.rolling_7d_avg) > 0.001
