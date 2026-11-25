-- How long agents wait for a human decision, by the UTC day the question was asked.
-- p50/p90 rather than the mean: the wait is long-tailed (a few questions sit overnight).
select
    cast(asked_at as date)                        as date_day,
    count(*)                                      as decisions,
    round(quantile_cont(wait_minutes, 0.5), 3)    as p50_minutes,
    round(quantile_cont(wait_minutes, 0.9), 3)    as p90_minutes
from {{ ref('int_decision_pairs') }}
group by 1
