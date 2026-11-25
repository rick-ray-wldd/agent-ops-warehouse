-- Exercise 2: work sessions per day (gaps and islands).
-- Read: stg_presence (presence_id, at_utc, kind). Only kind = 'heartbeat' matters.
-- A heartbeat more than 15 minutes after the previous heartbeat starts a new session.
-- A session runs from its first to its last heartbeat and belongs to the UTC day it started.
-- Return one row per day: date_day, sessions, total_minutes, longest_minutes (decimals, rounded to 3).
-- Hint (read only if stuck): flag the heartbeats that start a session, then a running sum of the flag
-- numbers the sessions.

select 'TODO' as date_day
