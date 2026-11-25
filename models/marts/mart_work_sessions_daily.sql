-- The human's working sessions per UTC day (a session belongs to the day it started).
select
    cast(started_at as date)   as date_day,
    count(*)                   as sessions,
    round(sum(minutes), 3)     as total_minutes,
    round(max(minutes), 3)     as longest_minutes
from {{ ref('int_work_sessions') }}
group by 1
