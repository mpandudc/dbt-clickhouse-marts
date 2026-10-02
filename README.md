# dbt-clickhouse-marts

dbt Core on ClickHouse: dimensional marts and daily mark-to-market PnL for a
multi-asset (crypto + IDX equity) trade ledger, with incremental loads that
stay idempotent under re-deliveries, reloads and backfills.

Part of the homelab data platform (Proxmox LXC 206). Self-contained: one
ClickHouse container plus a dbt runner image; no cloud services, no dbt
packages to download.

```
generator (seeded, per-day deterministic)
      │  CSV over ClickHouse HTTP, drop+insert per day partition
      ▼
raw.trades / raw.prices / raw.assets         (at-least-once, messy casing)
      │
      ▼  staging (views)
stg_trades  ── dedup by trade_id, normalise casing, signed qty, cash flow
stg_prices  ── one close per asset per trading day
stg_assets
      │
      ▼  intermediate (views)
int_position_daily   ── calendar spine per account/asset, running position + cash
int_position_valued  ── ASOF JOIN to latest close (IDX weekends carry Friday)
      │
      ▼  marts (MergeTree tables)
dim_assets · fact_trades (incremental delete+insert)
fct_daily_pnl · fct_account_daily_pnl
```

## PnL definition

`total_pnl = position_quantity × mark_price + cumulative_cash_flow`, where buys
and fees are negative cash. That is realised plus unrealised PnL net of fees,
with no lot-matching method needed. `daily_pnl` is the day-over-day change.
Currencies (USDT, IDR) are never summed together.

## Data quality built in

| Check | Where |
|---|---|
| Re-delivered trades collapse to one row | `stg_trades` + `unique` on `fact_trades.trade_id` |
| Every distinct raw trade lands in the fact | `tests/assert_fact_trades_complete.sql` |
| Running sum of `daily_pnl` equals `total_pnl` exactly | `tests/assert_daily_pnl_sums_to_total.sql` |
| Position cash flow equals sum of trade cash flows | `tests/assert_cash_flow_reconciles_to_trades.sql` |
| Spot positions never negative | `non_negative` on `int_position_daily` |
| Mark price no older than an IDX weekend | `accepted_values` (warn) |
| Dedup + cash-sign logic | dbt unit test on `stg_trades` |

## Run

Requires Docker with Compose and Python 3.12 on the host.

```bash
make check                 # offline: generator unit tests + project structure
make image up              # build dbt runner, start ClickHouse on :18123
make load DAYS=45          # generate and load 45 days from 2026-01-01
make build                 # dbt build: models + 30 data tests + unit test
make verify                # full runtime proof, writes results/verification.json
make clean
```

Backfill an explicit window:

```bash
docker compose run --rm dbt build --select fact_trades+ \
  --vars "{start_date: '2026-01-10', end_date: '2026-01-12'}"
```

Ports and credentials are overridable through `CLICKHOUSE_HTTP_PORT`,
`CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`. Defaults (`dbt`/`dbt`) are for a
local lab only.

## Design notes

- Loader drops and re-inserts a whole day partition, so loading the same day
  twice cannot duplicate raw rows; generator output for a day does not depend
  on the requested range.
- `fact_trades` re-reads `lookback_days` (default 3) on each run to absorb late
  re-deliveries; older corrections go through the explicit backfill vars.
- `mutations_sync: 2` in the profile makes delete+insert wait for the delete
  mutation before inserting.
- `generate_schema_name` is overridden so models land in flat ClickHouse
  databases `staging`, `intermediate`, `marts`.

See [VERIFICATION.md](VERIFICATION.md) for the recorded run.

Related: [airflow-data-orchestration](https://github.com/mpandudc/airflow-data-orchestration)
schedules this project; [homelab-data-platform](https://github.com/mpandudc/homelab-data-platform)
hosts the shared ClickHouse.
