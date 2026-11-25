# Exercises: write the three core models yourself

These three models are the heart of the warehouse, and the ones an interviewer is most likely to ask about. The pipeline already has working versions under `models/`, written with AI assistance. **Write your own first, without opening those files, notes or AI**, then grade it.

| # | File | Skill | Target time |
|---|---|---|---|
| 1 | `01_decision_wait.sql` | `LEAD` pairing inside a partition, `quantile_cont` | 20 min |
| 2 | `02_work_sessions.sql` | gaps and islands: `LAG`, a running `SUM` as a session id | 25 min |
| 3 | `03_rework_share.sql` | aggregate + window over the aggregate (`sum(count(*)) over ()`) | 10 min |

Each file says which tables you may read and exactly which columns to return. Then:

```
make exercises        # after `make build`; runs exercises/grade.py
```

The grader runs your SQL against the built warehouse and compares the result with `data/expected/metrics.json`. That file comes from an independent Python implementation in the generator, not from the dbt models, so matching it means your SQL is right, not just that it agrees with the AI's version.

Honesty rule for the résumé: list SQL as a skill only after you can pass all three from a blank file, without notes or AI, inside about 20 minutes each.
