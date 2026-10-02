with deduplicated as (
    select *
    from {{ source('raw', 'trades') }}
    -- Keep the first delivery of each trade; re-deliveries carry a later ingested_at.
    order by ingested_at asc
    limit 1 by trade_id
)

select
    trade_id,
    account_id,
    lower(asset_id) as asset_id,
    lower(side) as side,
    quantity,
    price,
    fee,
    executed_at,
    trade_date,
    ingested_at,
    if(lower(side) = 'buy', quantity, -quantity) as signed_quantity,
    toDecimal128(quantity * price, 8) as gross_notional,
    -- Cash leaving the account is negative: buys spend notional, every fill pays fee.
    toDecimal128(-signed_quantity * price - fee, 8) as cash_flow
from deduplicated
