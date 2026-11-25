-- Exercise 1: decision wait per day.
-- Read: fct_event (event_id, task_id, kind, event_time_utc).
-- A task's 'agent.needs_decision' is answered by the next 'human.decision' event on the same task.
-- Return one row per UTC day the question was asked:
--   date_day (DATE), decisions (count of answered questions), p50_minutes, p90_minutes
-- Minutes are wait times as decimals; use linear-interpolation percentiles (DuckDB quantile_cont), rounded to 3.
-- Hint (read only if stuck): within each task, order the two kinds by time and look one row ahead.

select 'TODO' as date_day
