-- Currencies are never summed together: one row per account, quote currency and day.
select
    account_id,
    quote_ccy,
    as_of_date,
    count() as positions,
    sum(trade_count) as trade_count,
    sum(market_value) as market_value,
    sum(cumulative_cash_flow) as cumulative_cash_flow,
    sum(total_pnl) as total_pnl,
    sum(daily_pnl) as daily_pnl
from {{ ref('fct_daily_pnl') }}
group by account_id, quote_ccy, as_of_date
