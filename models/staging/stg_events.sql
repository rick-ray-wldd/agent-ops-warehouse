-- One row per event_id. A redelivered event (same id in a later batch) keeps its first delivery.
with valid as (
    select * from {{ ref('stg_events__parsed') }}
    where event_time_utc is not null and kind is not null
),
ranked as (
    select
        *,
        row_number() over (partition by event_id order by loaded_at_utc, source_file) as delivery_rank
    from valid
)
select * exclude (delivery_rank, event_time_raw)
from ranked
where delivery_rank = 1
