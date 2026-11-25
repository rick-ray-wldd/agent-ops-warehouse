select
    rework_id,
    {{ utc_timestamp('at') }} as at_utc,
    task_id,
    stage
from {{ source('landing', 'rework') }}
qualify row_number() over (partition by rework_id order by loaded_at) = 1
