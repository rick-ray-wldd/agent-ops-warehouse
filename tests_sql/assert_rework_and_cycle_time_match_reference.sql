with expected_stage as (
    select unnest(rework_by_stage, recursive := true) from read_json_auto('data/expected/metrics.json')
),
expected_cycle as (
    select task_cycle_time.tasks as tasks, task_cycle_time.p50_minutes as p50, task_cycle_time.p90_minutes as p90
    from read_json_auto('data/expected/metrics.json')
)
select 'stage' as check_name, e.stage as detail
from expected_stage e
full join {{ ref('mart_rework_by_stage') }} a using (stage)
where a.rework_count is distinct from e.rework_count or abs(a.share_pct - e.share_pct) > 0.01
union all
select 'cycle', cast(a.tasks as varchar)
from {{ ref('mart_task_cycle_time') }} a, expected_cycle e
where a.tasks <> e.tasks or abs(a.p50_minutes - e.p50) > 0.001 or abs(a.p90_minutes - e.p90) > 0.001
