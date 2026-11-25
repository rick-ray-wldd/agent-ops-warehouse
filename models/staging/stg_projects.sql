select project_id, domain from {{ source('reference', 'projects') }}
