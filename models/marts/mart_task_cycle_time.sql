-- Cycle time: first time a task entered "working" to the last time it became "done".
with per_task as (
    select
        task_id,
        min(valid_from) filter (where state = 'working') as first_working,
        max(valid_from) filter (where state = 'done')    as last_done
    from {{ ref('fct_task_state_history') }}
    group by 1
),
done as (
    select date_diff('second', first_working, last_done) / 60.0 as cycle_minutes
    from per_task
    where first_working is not null and last_done is not null
)
select
    count(*)                                     as tasks,
    round(quantile_cont(cycle_minutes, 0.5), 3)  as p50_minutes,
    round(quantile_cont(cycle_minutes, 0.9), 3)  as p90_minutes
from done
