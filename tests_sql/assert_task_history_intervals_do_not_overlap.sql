-- SCD2: within a task, each interval must end exactly where the next one starts.
select task_id, valid_from, valid_to, next_from
from (
    select task_id, valid_from, valid_to,
           lead(valid_from) over (partition by task_id order by valid_from) as next_from
    from {{ ref('fct_task_state_history') }}
)
where next_from is not null and valid_to is distinct from next_from
