select
    assets.asset_id as asset_id,
    assets.symbol as symbol,
    assets.asset_class as asset_class,
    assets.quote_ccy as quote_ccy,
    assets.lot_size as lot_size,
    activity.first_trade_date as first_trade_date,
    activity.last_trade_date as last_trade_date,
    activity.trade_count as trade_count
from {{ ref('stg_assets') }} as assets
left join (
    select
        asset_id,
        min(trade_date) as first_trade_date,
        max(trade_date) as last_trade_date,
        count() as trade_count
    from {{ ref('stg_trades') }}
    group by asset_id
) as activity
    on assets.asset_id = activity.asset_id
