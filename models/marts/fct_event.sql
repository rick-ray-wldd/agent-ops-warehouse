{{ config(materialized='incremental', unique_key='event_id', incremental_strategy='delete+insert') }}
-- Grain: one row per event. Incremental on loaded_at (arrival), not event_time: a late event that happened
-- two days ago still arrives after the watermark, so it is picked up. Redeliveries are already removed in
-- staging; unique_key makes a rerun of the same batch idempotent.
select
    e.event_id,
    e.event_time_utc,
    cast(strftime(e.event_time_utc, '%Y%m%d') as integer) as date_key,
    e.kind,
    e.actor_id,
    a.agent_version_key,
    e.project_id,
    e.task_id,
    e.caused_by,
    e.gen_ai_system,
    e.gen_ai_request_model,
    e.gen_ai_usage_input_tokens,
    e.gen_ai_usage_output_tokens,
    e.loaded_at_utc
from {{ ref('stg_events') }} e
left join {{ ref('dim_agent') }} a
    on a.agent_id = e.actor_id
   and e.event_time_utc >= a.valid_from
   and (a.valid_to is null or e.event_time_utc < a.valid_to)
{% if is_incremental() %}
where e.loaded_at_utc > (select coalesce(max(loaded_at_utc), timestamp '1970-01-01') from {{ this }})
{% endif %}
