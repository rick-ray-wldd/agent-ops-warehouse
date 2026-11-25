with expected as (
    select unnest(work_sessions_daily, recursive := true) from read_json_auto('data/expected/metrics.json')
)
select e.day, e.sessions as expected_sessions, a.sessions as actual_sessions,
       e.total_minutes as expected_total, a.total_minutes as actual_total,
       e.longest_minutes as expected_longest, a.longest_minutes as actual_longest
from expected e
full join {{ ref('mart_work_sessions_daily') }} a on a.date_day = cast(e.day as date)
where a.date_day is null or e.day is null
   or a.sessions <> e.sessions
   or abs(a.total_minutes - e.total_minutes) > 0.001
   or abs(a.longest_minutes - e.longest_minutes) > 0.001
