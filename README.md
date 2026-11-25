# agent-ops-warehouse

A small, complete data warehouse for the event stream of a multi-agent AI workflow: coordinators dispatch tasks to writer agents, reviewers pass or send work back, and a human answers the questions agents raise. The warehouse answers one operational question end to end: **is the human waiting on the agents, or are the agents waiting on the human?**

> **Status:** the whole pipeline runs and passes (`make all`): 22 models, 34 data tests, and the incremental and full-refresh fact tables have the same fingerprint. Tested with Python 3.12, DuckDB 2.0.1, dbt-core 1.12.7 and dbt-duckdb 1.11.1. The same models were also run against a private, real event log of the same shape, read-only and kept out of this repo.

## Pipeline

```
generator (Python, seeded)  ->  data/raw/<table>/batch_<day>.csv      one batch per day, plus deliberate dirt
                            ->  data/expected/metrics.json            answer key from an independent Python implementation
scripts/land.py             ->  data/landing/...                      batches "arrive" over time
dbt staging                 ->  typed, UTC, de-duplicated; malformed rows quarantined in stg_events__rejected
dbt marts                   ->  star schema: fct_event (incremental) + dim_agent (SCD2) + dim_project + dim_date
                                + dim_event_kind; fct_task_state_history (SCD2)
dbt metric marts            ->  decision wait p50/p90 · work sessions (gaps and islands) · 7-day rolling volume
                                · rework share by stage · task cycle time
dbt tests                   ->  keys, relationships, accepted values, SCD2 integrity, and every metric against the answer key
```

One command runs all of it (`make all`): generate → first load (40 days) → incremental load of the rest → full refresh, which must produce a byte-identical fact table → all tests.

## What it demonstrates

- **Dimensional modelling:** one event per row in `fct_event`, conformed dimensions, a date spine so empty days still exist.
- **SCD Type 2, twice:** task state over time (`fct_task_state_history`), and which model and effort each agent ran at any moment (`dim_agent`), so "which model was the writer on when this shipped?" is a join, not a guess.
- **Incremental loading done right:** the watermark is *arrival* time (`loaded_at`), not event time, so an event that happened two days ago but arrived today is still picked up. Redeliveries are de-duplicated, and the run is idempotent. The pipeline proves it: incremental and full-refresh fact tables must have the same fingerprint.
- **Dirty data handled on purpose:** duplicate deliveries, late arrivals, rows with no timestamp, impossible UTC offsets, and mixed `+00:00`/`+08:00` offsets. Timestamps are parsed by hand to UTC, with no timezone extension; bad rows are quarantined and counted, not silently dropped.
- **Window functions:** `LEAD` pairing, gaps and islands with `LAG` and a running `SUM`, trailing averages, a share of the total in one pass, `quantile_cont`.
- **Testing against an oracle:** every metric is checked against `data/expected/metrics.json`, which the generator computes in plain Python from the clean truth, so the SQL is verified by a second, independent implementation.

## Run it

```
make generate          # standard library only
make test-generator    # generator and project-structure tests (standard library)
make venv              # once: Python 3.12 venv with duckdb, dbt-core, dbt-duckdb (~44 MB)
make all               # the whole pipeline
make exercises         # grade your own versions of the three core models (see exercises/)
```

## Docs

- `docs/DESIGN.md`: decisions and trade-offs (why a star schema, why arrival-time watermarks, why hand-parsed offsets).
- `docs/ERD.md`: tables, grain and keys.
- `docs/METRICS.md`: exact metric definitions.
- `exercises/`: the three core models to write from a blank file, with a grader.

## Data and privacy

All data is **synthetic**. The generator's parameters (`generator/params.json`) are invented round numbers, not taken from any real system. Agents, projects and models have neutral names (`agent_01`, `project_alpha`, `model-a-large`). There is no free text, no account, path or identifier from any real workspace.

## How it was built

Designed and directed by the author; built with AI coding agents. The three core models in `exercises/` are meant to be rewritten by hand from a blank file. See `exercises/README.md`.

## License and credits

No license has been chosen for this project yet; the owner will choose one before it is published. `NOTICE` covers only the upstream work it builds on.

The project layout (dbt-core + dbt-duckdb, `models/staging` → marts, a local DuckDB profile) follows dbt-labs' `jaffle_shop_duckdb` (Apache-2.0); see `NOTICE`. Event attribute names follow the OpenTelemetry GenAI semantic conventions where they apply.
