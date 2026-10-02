-- One row per account, asset and calendar day from the first trade until the
-- latest price date, so positions carry across days without trades.
with daily as (
    select
        account_id,
        asset_id,
        trade_date as as_of_date,
        sum(signed_quantity) as quantity_change,
        sum(cash_flow) as cash_flow,
        count() as trade_count
    from {{ ref('stg_trades') }}
    group by account_id, asset_id, trade_date
),

bounds as (
    select account_id, asset_id, min(as_of_date) as first_date
    from daily
    group by account_id, asset_id
),

calendar_end as (
    select max(price_date) as last_date from {{ ref('stg_prices') }}
),

spine as (
    select
        bounds.account_id as account_id,
        bounds.asset_id as asset_id,
        arrayJoin(
            arrayMap(
                day_offset -> bounds.first_date + day_offset,
                range(toUInt32(dateDiff('day', bounds.first_date, calendar_end.last_date) + 1))
            )
        ) as as_of_date
    from bounds
    cross join calendar_end
),

joined as (
    -- ClickHouse fills unmatched LEFT JOIN columns with type defaults (0), which
    -- is exactly "no trades that day".
    select
        spine.account_id as account_id,
        spine.asset_id as asset_id,
        spine.as_of_date as as_of_date,
        daily.quantity_change as quantity_change,
        daily.cash_flow as cash_flow,
        daily.trade_count as trade_count
    from spine
    left join daily
        on spine.account_id = daily.account_id
        and spine.asset_id = daily.asset_id
        and spine.as_of_date = daily.as_of_date
)

select
    account_id,
    asset_id,
    as_of_date,
    quantity_change,
    cash_flow,
    trade_count,
    sum(quantity_change) over running as position_quantity,
    sum(cash_flow) over running as cumulative_cash_flow
from joined
window running as (
    partition by account_id, asset_id
    order by as_of_date
    rows between unbounded preceding and current row
)
