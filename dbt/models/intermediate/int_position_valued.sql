-- Mark each daily position with the latest close on or before that day. IDX
-- has no weekend closes, so Saturday and Sunday carry Friday's price.
select
    position.account_id as account_id,
    position.asset_id as asset_id,
    position.as_of_date as as_of_date,
    position.quantity_change as quantity_change,
    position.cash_flow as cash_flow,
    position.trade_count as trade_count,
    position.position_quantity as position_quantity,
    position.cumulative_cash_flow as cumulative_cash_flow,
    price.close as mark_price,
    price.price_date as mark_price_date,
    dateDiff('day', price.price_date, position.as_of_date) as mark_price_age_days
from {{ ref('int_position_daily') }} as position
asof left join {{ ref('stg_prices') }} as price
    on position.asset_id = price.asset_id
    and position.as_of_date >= price.price_date
