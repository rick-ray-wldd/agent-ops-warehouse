-- SCD Type 2 over task state: every change opens an interval that the next change closes.
select
    task_id,
    state,
    owner_agent_id,
    changed_at_utc as valid_from,
    lead(changed_at_utc) over (partition by task_id order by changed_at_utc, change_id) as valid_to,
    lead(changed_at_utc) over (partition by task_id order by changed_at_utc, change_id) is null as is_current,
    date_diff('second', changed_at_utc,
              lead(changed_at_utc) over (partition by task_id order by changed_at_utc, change_id)) / 60.0
        as duration_minutes
from {{ ref('stg_task_changes') }}
