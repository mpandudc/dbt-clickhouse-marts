# Verification evidence

Verified on 2026-10-02 (Asia/Jakarta) with `make check` and `make verify`.

- Host: Proxmox LXC 206 `data` (4 vCPU, 8 GB RAM, Ubuntu 24.04), Docker 29.1.3.
- ClickHouse 26.8.15.10, dbt-core 1.12.5, dbt-clickhouse 1.10.3.
- Offline checks: 6 generator unit tests passed; 9 models documented.
- `dbt build --full-refresh` on 40 days: PASS=40 (9 models, 30 data tests,
  1 unit test), 15.6 s wall clock including container start.
- Raw had 1,451 trade rows for 1,417 distinct trade IDs; `fact_trades` had
  exactly 1,417 rows.
- Incremental rerun with no new data: all mart counts and latest PnL identical.
- Reloading the last 5 days: identical.
- Appending 5 new days: fact grew to 1,596 rows = 1,596 distinct raw trades,
  PnL reached 2026-02-14.
- Backfill of 2026-01-10 via `--vars start_date/end_date`: PASS=7, all counts
  and PnL identical to before.

- dbt docs web UI (`docs` service) served the site and a catalog containing
  `fct_daily_pnl` on :18090. (Re-run 2026-10-02 22:13 with identical results.)

Raw numbers: [results/verification.json](results/verification.json).

The PnL values come from seeded synthetic data and carry no market meaning;
they are recorded only to show that reruns reproduce them exactly.
