-- Landing tables. One partition per day so a reload can drop and replace a
-- single day without touching the rest of the history.
CREATE DATABASE IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.assets
(
    asset_id    String,
    symbol      String,
    asset_class LowCardinality(String),
    quote_ccy   LowCardinality(String),
    lot_size    Decimal(38, 8),
    loaded_at   DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY asset_id;

CREATE TABLE IF NOT EXISTS raw.prices
(
    price_date Date,
    asset_id   String,
    close      Decimal(38, 8),
    loaded_at  DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(price_date)
ORDER BY (asset_id, price_date);

CREATE TABLE IF NOT EXISTS raw.trades
(
    trade_id    String,
    account_id  String,
    asset_id    String,
    side        String,
    quantity    Decimal(38, 8),
    price       Decimal(38, 8),
    fee         Decimal(38, 8),
    executed_at DateTime64(3, 'UTC'),
    trade_date  Date,
    ingested_at DateTime64(3, 'UTC'),
    loaded_at   DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(trade_date)
ORDER BY (trade_date, trade_id);
