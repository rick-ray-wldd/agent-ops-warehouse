# Metric definitions

All days are UTC dates. Minutes are decimals rounded to 3 places; shares are percentages rounded to 2. Percentiles use linear interpolation (DuckDB `quantile_cont`; the same rule as the Python answer key).

| Metric | Model | Definition |
|---|---|---|
| Decision wait | `mart_decision_wait_daily` | For each `agent.needs_decision` event, the next event on the same task among {`agent.needs_decision`, `human.decision`}; if it is a `human.decision`, the wait is the time between them. Grouped by the day the question was asked: count, p50, p90. |
| Work sessions | `mart_work_sessions_daily` | Human heartbeats ordered in time; a gap longer than `session_gap_minutes` (15) starts a new session. A session lasts from its first to its last heartbeat and belongs to the day it started. Per day: sessions, total minutes, longest session. |
| Event volume | `mart_event_volume_daily` | Events per day on the calendar spine (zero if none), with the average over that day and the 6 days before it (fewer at the start of the range). |
| Rework by stage | `mart_rework_by_stage` | Count of rework records per stage (dispatch, execution, review) and each stage's share of all rework. |
| Task cycle time | `mart_task_cycle_time` | Per task: the first time it entered `working` to the last time it entered `done`; across finished tasks: count, p50, p90. |
| Volume anomaly (warn) | `warn_daily_volume_outside_band` | A day more than `volume_band_pct` (50%) away from its trailing 7-day average. Warns only; it usually means a missing batch. |
