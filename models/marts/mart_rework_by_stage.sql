-- Where reviews sent work back, and each stage's share of all rework.
select
    stage,
    count(*)                                                    as rework_count,
    round(100.0 * count(*) / sum(count(*)) over (), 2)          as share_pct
from {{ ref('stg_rework') }}
group by 1
