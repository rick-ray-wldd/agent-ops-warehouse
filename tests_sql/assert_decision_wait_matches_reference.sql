-- The SQL p50/p90 must equal the independent Python answer key (data/expected/metrics.json).
with expected as (
    select unnest(decision_wait_daily, recursive := true) from read_json_auto('data/expected/metrics.json')
)
select e.day, e.decisions, a.decisions as actual_decisions, e.p50_minutes, a.p50_minutes as actual_p50,
       e.p90_minutes, a.p90_minutes as actual_p90
from expected e
full join {{ ref('mart_decision_wait_daily') }} a on a.date_day = cast(e.day as date)
where a.date_day is null or e.day is null
   or a.decisions <> e.decisions
   or abs(a.p50_minutes - e.p50_minutes) > 0.001
   or abs(a.p90_minutes - e.p90_minutes) > 0.001
