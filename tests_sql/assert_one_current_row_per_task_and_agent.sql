-- SCD2: exactly one open (current) row per task and per agent.
select 'task' as entity, task_id as id, count(*) filter (where is_current) as current_rows
from {{ ref('fct_task_state_history') }} group by 1, 2 having current_rows <> 1
union all
select 'agent', agent_id, count(*) filter (where is_current)
from {{ ref('dim_agent') }} group by 1, 2 having count(*) filter (where is_current) <> 1
