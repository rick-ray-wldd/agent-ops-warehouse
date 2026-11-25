select event_id, event_time_utc, loaded_at_utc
from {{ ref('fct_event') }}
where event_time_utc > loaded_at_utc
