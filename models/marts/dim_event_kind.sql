-- Kind -> who acts and whether it is a step in a task's lifecycle.
select
    kind,
    split_part(kind, '.', 1) as actor_type,
    kind in ('task.dispatched', 'agent.needs_decision', 'human.decision', 'agent.done',
             'review.passed', 'review.blocked') as is_lifecycle_step
from (select distinct kind from {{ ref('stg_events') }})
