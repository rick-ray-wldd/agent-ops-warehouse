-- Every landed event row, typed. Nothing is dropped here; stg_events and stg_events__rejected split it.
select
    event_id,
    nullif(kind, '')                                              as kind,
    nullif(actor_id, '')                                          as actor_id,
    nullif(project_id, '')                                        as project_id,
    nullif(task_id, '')                                           as task_id,
    nullif(caused_by, '')                                         as caused_by,
    nullif(gen_ai_system, '')                                     as gen_ai_system,
    nullif(gen_ai_request_model, '')                              as gen_ai_request_model,
    try_cast(nullif(gen_ai_usage_input_tokens, '') as integer)    as gen_ai_usage_input_tokens,
    try_cast(nullif(gen_ai_usage_output_tokens, '') as integer)   as gen_ai_usage_output_tokens,
    nullif(event_time, '')                                        as event_time_raw,
    {{ utc_timestamp("nullif(event_time, '')") }}                 as event_time_utc,
    {{ utc_timestamp('loaded_at') }}                              as loaded_at_utc,
    filename                                                      as source_file
from {{ source('landing', 'events') }}
