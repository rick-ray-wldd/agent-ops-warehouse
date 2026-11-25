select agent_id, role, nullif(provider, '') as provider
from {{ source('reference', 'agents') }}
