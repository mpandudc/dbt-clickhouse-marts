select
    price_date,
    lower(asset_id) as asset_id,
    close
from {{ source('raw', 'prices') }}
-- A reloaded partition never duplicates, but guard the grain anyway.
order by loaded_at desc
limit 1 by asset_id, price_date
