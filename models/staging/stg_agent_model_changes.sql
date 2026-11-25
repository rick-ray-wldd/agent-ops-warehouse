select agent_id, {{ utc_timestamp('valid_from') }} as valid_from_utc, model, effort
from {{ source('reference', 'agent_model_changes') }}
