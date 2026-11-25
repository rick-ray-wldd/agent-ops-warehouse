select
    presence_id,
    {{ utc_timestamp('"at"') }}        as at_utc,
    kind,
    {{ utc_timestamp('loaded_at') }} as loaded_at_utc
from {{ source('landing', 'presence') }}
qualify row_number() over (partition by presence_id order by loaded_at) = 1
