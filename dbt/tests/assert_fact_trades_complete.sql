-- Every distinct raw trade_id must land in the fact exactly once.
select missing
from (
    select
        (select uniqExact(trade_id) from {{ source('raw', 'trades') }})
        - (select count() from {{ ref('fact_trades') }}) as missing
)
where missing != 0
