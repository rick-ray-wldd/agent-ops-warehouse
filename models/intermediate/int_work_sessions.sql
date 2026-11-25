-- Gaps and islands: a heartbeat more than session_gap_minutes after the previous one starts a new session.
with beats as (
    select
        at_utc,
        case
            when lag(at_utc) over (order by at_utc) is null then 1
            when date_diff('second', lag(at_utc) over (order by at_utc), at_utc) > {{ var('session_gap_minutes') }} * 60 then 1
            else 0
        end as starts_session
    from {{ ref('stg_presence') }}
    where kind = 'heartbeat'
),
numbered as (
    select at_utc, sum(starts_session) over (order by at_utc rows unbounded preceding) as session_id
    from beats
)
select
    session_id,
    min(at_utc) as started_at,
    max(at_utc) as ended_at,
    date_diff('second', min(at_utc), max(at_utc)) / 60.0 as minutes
from numbered
group by session_id
