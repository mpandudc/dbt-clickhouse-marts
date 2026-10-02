-- The running sum of daily_pnl must equal total_pnl on every row; decimals
-- make this an exact comparison.
select account_id, asset_id, as_of_date, total_pnl, running_daily_pnl
from (
    select
        account_id,
        asset_id,
        as_of_date,
        total_pnl,
        sum(daily_pnl) over (
            partition by account_id, asset_id
            order by as_of_date
            rows between unbounded preceding and current row
        ) as running_daily_pnl
    from {{ ref('fct_daily_pnl') }}
)
where running_daily_pnl != total_pnl
