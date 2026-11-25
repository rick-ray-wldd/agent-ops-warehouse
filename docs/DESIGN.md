# Design

## The question
In a workflow where AI agents do the work and one human approves, the bottleneck moves. Sometimes agents wait for a human decision; sometimes the human waits for agents to finish or for a review to pass. The warehouse measures both sides: how long questions wait for the human, when the human is actually working, how often reviews send work back and at which stage, and how long a task takes end to end.

## Sources (as an exporter would deliver them)
| Source | Grain | Arrives |
|---|---|---|
| events | one action by an agent or the human | daily batch, next morning |
| presence | a heartbeat while the human is at the desk | daily batch |
| task_changes | a task moving to a new state | daily batch |
| rework | a review sending work back, with the stage at fault | daily batch |
| agents, agent_model_changes, projects | reference data | full file each time |

The generator writes these as CSV; everything lands as text, and staging owns the types. A bad value is then rejected in staging instead of failing the whole load.

## Decisions
1. **Star schema with one wide fact.** `fct_event` is one row per event; dimensions describe who acted (`dim_agent`), where (`dim_project`), when (`dim_date`) and what kind (`dim_event_kind`). Metric marts read from the fact, so every metric shares one definition of "an event".
2. **Two SCD Type 2 histories.**
   - `fct_task_state_history`: each state change opens an interval; the next change closes it. Cycle time and "time spent blocked" come from intervals, not from guessing between events.
   - `dim_agent`: agents change models over time (a model is swapped when quota runs low, for example). The fact joins to the agent *version* in force at event time, so per-model comparisons are not polluted by later changes.
3. **Incremental on arrival time.** The watermark is `loaded_at`. Event time is wrong for this: a late event has an old event time and would be skipped forever. `unique_key = event_id` with delete+insert makes reruns idempotent. The pipeline checks that the incremental result equals a full refresh.
4. **De-duplicate in staging, keep the first delivery.** The same `event_id` may arrive twice; the earliest load wins, so a later copy can never move an event.
5. **Quarantine, don't drop.** Rows with no timestamp, an unparsable timestamp or no kind go to `stg_events__rejected` with a reason. A test checks their count equals what the exporter produced. Silent drops are how pipelines lose data without anyone noticing.
6. **UTC parsed by hand.** Offsets like `+08:00` are applied in SQL (`macros/utc_timestamp.sql`). This avoids depending on a timezone extension, and it rejects impossible offsets (`+99:99`) instead of guessing.
7. **Percentiles, not means.** Decision wait is long-tailed: most questions are answered in minutes, a few overnight. p50 and p90 describe it; the mean does not.
8. **An oracle for every metric.** The generator computes each metric in plain Python from the clean truth (`data/expected/metrics.json`). The dbt tests compare the marts with it, so the SQL is checked by an independent implementation, not by itself.
9. **Days are UTC.** Reporting in a local timezone is a presentation choice; keeping the warehouse in UTC avoids double conversions. A local-time view can be added on top.

## Event attributes
Agent events carry model metadata named after the OpenTelemetry GenAI semantic conventions: `gen_ai_system` (provider), `gen_ai_request_model`, `gen_ai_usage_input_tokens`, `gen_ai_usage_output_tokens`. Dots become underscores in column names. The provider attribute has been renamed in newer versions of the conventions, so check the current spec before publishing.

## What the real data taught
The same models were run once against a private, real event log of the same shape (read-only, aggregates only, nothing kept). Two things only show up on real data:
- **Heartbeats are not presence.** The real presence sampler keeps beating while the person is away, so gaps-and-islands on heartbeats alone merges whole weeks into one "session". On real data, sessions should come from the explicit away/back events. The synthetic data only beats during work blocks, which is why the simple rule works there: an example of a test set that is too kind.
- **Categories grow.** Real rework records use a fourth stage that the synthetic data never produces. The accepted-values test is what catches that; it should fail loudly, not be widened silently.

## What is out of scope
- Real-time streaming: batches are daily. The same models would sit behind a streaming ingest (for example Kafka into a lakehouse table); the modelling and tests would not change.
- Cost in money: token counts are kept; prices change and belong in a separate, dated price table.
