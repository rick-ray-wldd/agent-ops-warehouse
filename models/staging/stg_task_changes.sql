select
    change_id,
    task_id,
    {{ utc_timestamp('changed_at') }} as changed_at_utc,
    state,
    nullif(owner_agent_id, '')        as owner_agent_id,
    {{ utc_timestamp('loaded_at') }}  as loaded_at_utc
from {{ source('landing', 'task_changes') }}
qualify row_number() over (partition by change_id order by loaded_at) = 1
