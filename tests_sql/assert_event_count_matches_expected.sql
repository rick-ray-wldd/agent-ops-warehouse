-- After dedupe and rejection, the fact table holds exactly the generator's true events.
with expected as (select counts.events as n from read_json_auto('data/expected/metrics.json'))
select (select count(*) from {{ ref('fct_event') }}) as actual, n as expected
from expected
where (select count(*) from {{ ref('fct_event') }}) <> n
