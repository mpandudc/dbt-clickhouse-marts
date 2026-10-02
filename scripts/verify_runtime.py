"""End-to-end runtime verification against a real ClickHouse container.

Proves: full build passes every test, an incremental rerun changes nothing,
reloading already-loaded days changes nothing, new days append exactly the new
distinct trades, and an explicit backfill window rebuilds without duplicates.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from load_raw import ClickHouse  # noqa: E402

START = date(2026, 1, 1)
CH = ClickHouse("http://localhost:18123", "dbt", "dbt")


def sh(*args: str) -> str:
    print("+", " ".join(args), flush=True)
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        print(result.stdout[-4000:], result.stderr[-4000:], sep="\n")
        raise SystemExit(f"command failed: {' '.join(args)}")
    return result.stdout


def load(start: date, days: int) -> None:
    sh("docker", "compose", "run", "--rm", "--entrypoint", "python", "dbt",
       "/app/scripts/load_raw.py", "--start", start.isoformat(), "--days", str(days))


def dbt(*args: str) -> str:
    out = sh("docker", "compose", "run", "--rm", "dbt", *args)
    summary = [line for line in out.splitlines() if "Done. PASS=" in line]
    print(summary[-1] if summary else out[-2000:])
    return out


def snapshot() -> dict:
    q = CH.scalar
    return {
        "raw_trade_rows": int(q("select count() from raw.trades")),
        "raw_distinct_trades": int(q("select uniqExact(trade_id) from raw.trades")),
        "fact_trades": int(q("select count() from marts.fact_trades")),
        "fact_distinct_trades": int(q("select uniqExact(trade_id) from marts.fact_trades")),
        "daily_pnl_rows": int(q("select count() from marts.fct_daily_pnl")),
        "max_as_of_date": q("select max(as_of_date) from marts.fct_daily_pnl"),
        "latest_total_pnl_by_ccy": q(
            "select groupArray((quote_ccy, toString(total))) from ("
            " select quote_ccy, sum(total_pnl) as total from marts.fct_account_daily_pnl"
            " where as_of_date = (select max(as_of_date) from marts.fct_account_daily_pnl)"
            " group by quote_ccy order by quote_ccy)"
        ),
    }


def expect(condition: bool, message: str) -> None:
    print(("PASS " if condition else "FAIL ") + message, flush=True)
    if not condition:
        raise SystemExit(message)


def main() -> None:
    evidence: dict = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    sh("docker", "compose", "down", "--volumes", "--remove-orphans")
    sh("docker", "compose", "--profile", "tools", "build", "dbt")
    sh("docker", "compose", "up", "-d", "--wait", "clickhouse")
    evidence["versions"] = {
        "clickhouse": CH.scalar("select version()"),
        "dbt": [line.strip() for line in dbt("--version").splitlines() if line.strip()][:6],
    }

    load(START, 40)
    started = time.monotonic()
    dbt("build", "--full-refresh")
    evidence["full_build_seconds"] = round(time.monotonic() - started, 1)
    base = snapshot()
    evidence["after_full_build"] = base
    expect(base["fact_trades"] == base["raw_distinct_trades"], "fact has one row per distinct raw trade")
    expect(base["raw_trade_rows"] > base["raw_distinct_trades"], "raw contains re-deliveries to deduplicate")

    dbt("build")
    expect(snapshot() == base, "incremental rerun with no new data changes nothing")

    load(START + timedelta(days=35), 5)
    dbt("build")
    expect(snapshot() == base, "reloading the last five days changes nothing")

    load(START + timedelta(days=40), 5)
    dbt("build")
    grown = snapshot()
    evidence["after_append"] = grown
    expect(grown["fact_trades"] == grown["raw_distinct_trades"], "append keeps one row per distinct trade")
    expect(grown["fact_trades"] > base["fact_trades"], "five new days add trades")
    expect(grown["max_as_of_date"] == (START + timedelta(days=44)).isoformat(), "PnL reaches the new last day")

    load(START + timedelta(days=9), 1)
    dbt("build", "--select", "fact_trades+", "--vars", "{start_date: '2026-01-10', end_date: '2026-01-10'}")
    expect(snapshot() == grown, "explicit backfill window rebuilds a past day without duplicates")

    sh("docker", "compose", "--profile", "docs", "up", "-d", "docs")
    docs_ok = False
    for _ in range(60):
        try:
            with urllib.request.urlopen("http://localhost:18090/", timeout=5) as response:
                docs_ok = response.status == 200 and b"dbt" in response.read()
            with urllib.request.urlopen("http://localhost:18090/catalog.json", timeout=5) as response:
                docs_ok = docs_ok and b"fct_daily_pnl" in response.read()
            break
        except OSError:
            time.sleep(2)
    expect(docs_ok, "dbt docs web UI serves the catalog on :18090")

    evidence["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    out = ROOT / "results" / "verification.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"evidence written to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
