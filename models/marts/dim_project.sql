select project_id, domain from {{ ref('stg_projects') }}
