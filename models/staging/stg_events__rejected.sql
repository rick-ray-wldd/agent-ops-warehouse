-- Rows that cannot become events: no timestamp, an unparsable timestamp, or no kind. Kept, not deleted,
-- so the count can be tested and the exporter fixed.
select
    *,
    case
        when event_time_raw is null then 'missing_event_time'
        when event_time_utc is null then 'unparsable_event_time'
        when kind is null then 'missing_kind'
    end as reject_reason
from {{ ref('stg_events__parsed') }}
where event_time_utc is null or kind is null
