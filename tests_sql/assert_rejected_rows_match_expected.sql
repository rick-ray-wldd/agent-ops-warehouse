-- Every malformed row the exporter produced is rejected, and nothing else is.
with expected as (
    select counts.malformed_rows as n from read_json_auto('data/expected/metrics.json')
)
select (select count(*) from {{ ref('stg_events__rejected') }}) as rejected, n as expected
from expected
where (select count(*) from {{ ref('stg_events__rejected') }}) <> n
