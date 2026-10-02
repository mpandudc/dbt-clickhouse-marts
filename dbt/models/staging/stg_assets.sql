select
    lower(asset_id) as asset_id,
    upper(symbol) as symbol,
    asset_class,
    quote_ccy,
    lot_size
from {{ source('raw', 'assets') }} final
