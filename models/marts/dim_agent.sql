-- SCD Type 2: one row per agent per model/effort setting, with the period it was in force.
-- "Which model was the writer on when this shipped?" is a join on event time inside [valid_from, valid_to).
with versions as (
    select
        c.agent_id, a.role, a.provider, c.model, c.effort,
        c.valid_from_utc as valid_from,
        lead(c.valid_from_utc) over (partition by c.agent_id order by c.valid_from_utc) as valid_to
    from {{ ref('stg_agent_model_changes') }} c
    join {{ ref('stg_agents') }} a using (agent_id)
),
human as (
    select agent_id, role, provider, null as model, null as effort,
           timestamp '1900-01-01' as valid_from, null::timestamp as valid_to
    from {{ ref('stg_agents') }} where role = 'human'
)
select
    md5(agent_id || '|' || cast(valid_from as varchar)) as agent_version_key,
    *,
    valid_to is null as is_current
from (select * from versions union all select * from human)
