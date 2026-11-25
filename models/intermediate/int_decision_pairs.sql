-- A question to the human and the decision that answers it, paired with LEAD over the task's own timeline.
with steps as (
    select
        task_id, event_id, kind, event_time_utc,
        lead(kind)           over w as next_kind,
        lead(event_time_utc) over w as next_time
    from {{ ref('fct_event') }}
    where kind in ('agent.needs_decision', 'human.decision') and task_id is not null
    window w as (partition by task_id order by event_time_utc, event_id)
)
select
    task_id,
    event_id                                                   as question_event_id,
    event_time_utc                                             as asked_at,
    next_time                                                  as decided_at,
    date_diff('millisecond', event_time_utc, next_time) / 60000.0 as wait_minutes
from steps
where kind = 'agent.needs_decision' and next_kind = 'human.decision'
