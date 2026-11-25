# Tables, grain and keys

```mermaid
erDiagram
    dim_date ||--o{ fct_event : "date_key"
    dim_project ||--o{ fct_event : "project_id"
    dim_agent ||--o{ fct_event : "agent_version_key (version in force at event time)"
    dim_event_kind ||--o{ fct_event : "kind"
    fct_event ||--o{ int_decision_pairs : "question_event_id"
    fct_task_state_history }o--|| fct_event : "task_id"

    fct_event {
        varchar event_id PK
        timestamp event_time_utc
        int date_key FK
        varchar kind FK
        varchar actor_id
        varchar agent_version_key FK
        varchar project_id FK
        varchar task_id
        varchar caused_by
        varchar gen_ai_system
        varchar gen_ai_request_model
        int gen_ai_usage_input_tokens
        int gen_ai_usage_output_tokens
        timestamp loaded_at_utc
    }
    dim_agent {
        varchar agent_version_key PK
        varchar agent_id
        varchar role
        varchar provider
        varchar model
        varchar effort
        timestamp valid_from
        timestamp valid_to
        boolean is_current
    }
    fct_task_state_history {
        varchar task_id
        varchar state
        varchar owner_agent_id
        timestamp valid_from
        timestamp valid_to
        boolean is_current
        double duration_minutes
    }
    dim_project {
        varchar project_id PK
        varchar domain
    }
    dim_date {
        int date_key PK
        date date_day
        int day_of_week
        boolean is_weekend
        date week_start
    }
    dim_event_kind {
        varchar kind PK
        varchar actor_type
        boolean is_lifecycle_step
    }
```

| Model | Grain | Built as |
|---|---|---|
| `stg_events` | one event_id (first delivery) | view |
| `stg_events__rejected` | one malformed landed row | view |
| `fct_event` | one event | incremental table |
| `fct_task_state_history` | one task state interval | table |
| `dim_agent` | one agent model/effort version | table |
| `int_decision_pairs` | one answered question | view |
| `int_work_sessions` | one work session | view |
| `mart_*` | one day, one stage or one summary row | table |
