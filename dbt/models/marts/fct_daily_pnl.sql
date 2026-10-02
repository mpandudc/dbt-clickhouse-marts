-- Mark-to-market PnL. total_pnl = market value + cumulative cash flow, where
-- buys and fees are negative cash. It therefore includes realised and
-- unrealised PnL net of fees without needing a lot-matching method.
with valued as (
    select
        positions.account_id as account_id,
        positions.asset_id as asset_id,
        assets.asset_class as asset_class,
        assets.quote_ccy as quote_ccy,
        positions.as_of_date as as_of_date,
        positions.trade_count as trade_count,
        positions.position_quantity as position_quantity,
        positions.mark_price as mark_price,
        positions.mark_price_date as mark_price_date,
        toDecimal128(positions.position_quantity * positions.mark_price, 8) as market_value,
        positions.cumulative_cash_flow as cumulative_cash_flow
    from {{ ref('int_position_valued') }} as positions
    inner join {{ ref('stg_assets') }} as assets
        on positions.asset_id = assets.asset_id
),

with_total as (
    select
        *,
        toDecimal128(market_value + cumulative_cash_flow, 8) as total_pnl
    from valued
)

select
    *,
    toDecimal128(
        total_pnl - lagInFrame(total_pnl, 1, toDecimal128(0, 8)) over (
            partition by account_id, asset_id
            order by as_of_date
            rows between unbounded preceding and unbounded following
        ),
        8
    ) as daily_pnl
from with_total
