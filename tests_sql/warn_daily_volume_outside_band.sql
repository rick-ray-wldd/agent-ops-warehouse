{{ config(severity='warn') }}
-- Anomaly check, warn only: a day this far from its trailing 7-day average usually means a missing batch.
select date_day, events, rolling_7d_avg
from {{ ref('mart_event_volume_daily') }}
where rolling_7d_avg > 0
  and abs(events - rolling_7d_avg) / rolling_7d_avg * 100 > {{ var('volume_band_pct') }}
