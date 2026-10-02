-- Latest cumulative cash flow per position must equal the sum of trade cash flows.
with from_trades as (
    select account_id, asset_id, sum(cash_flow) as cash_flow
    from {{ ref('fact_trades') }}
    group by account_id, asset_id
),

from_pnl as (
    select account_id, asset_id, argMax(cumulative_cash_flow, as_of_date) as cash_flow
    from {{ ref('fct_daily_pnl') }}
    group by account_id, asset_id
)

select
    from_trades.account_id as account_id,
    from_trades.asset_id as asset_id,
    from_trades.cash_flow as trade_cash_flow,
    from_pnl.cash_flow as pnl_cash_flow
from from_trades
full outer join from_pnl
    on from_trades.account_id = from_pnl.account_id
    and from_trades.asset_id = from_pnl.asset_id
where from_trades.cash_flow != from_pnl.cash_flow
