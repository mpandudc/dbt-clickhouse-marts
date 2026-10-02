{{
    config(
        materialized='incremental',
        incremental_strategy='delete+insert',
        unique_key='trade_id',
        engine='MergeTree()',
        order_by='(trade_date, trade_id)',
        partition_by='toYYYYMM(trade_date)',
    )
}}

{#- Normal runs re-read the last `lookback_days` days to absorb re-deliveries.
    A backfill passes --vars '{start_date: ..., end_date: ...}' to rebuild an
    explicit window instead. -#}
select
    trades.trade_id as trade_id,
    trades.account_id as account_id,
    trades.asset_id as asset_id,
    assets.symbol as symbol,
    assets.asset_class as asset_class,
    assets.quote_ccy as quote_ccy,
    trades.side as side,
    trades.quantity as quantity,
    trades.signed_quantity as signed_quantity,
    trades.price as price,
    trades.gross_notional as gross_notional,
    trades.fee as fee,
    trades.cash_flow as cash_flow,
    trades.executed_at as executed_at,
    trades.trade_date as trade_date,
    trades.ingested_at as ingested_at
from {{ ref('stg_trades') }} as trades
inner join {{ ref('stg_assets') }} as assets
    on trades.asset_id = assets.asset_id
{% if var('start_date', none) is not none %}
where trades.trade_date between toDate('{{ var("start_date") }}') and toDate('{{ var("end_date", var("start_date")) }}')
{% elif is_incremental() %}
where trades.trade_date >= (select max(trade_date) from {{ this }}) - {{ var('lookback_days') }}
{% endif %}
