"""Load generated days into ClickHouse raw tables over the HTTP interface.

Each day is loaded by dropping its partition and inserting it again, so running
the loader twice for the same date leaves exactly one copy of that day.
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generator"))

from generate import ASSET_FIELDS, PRICE_FIELDS, TRADE_FIELDS, asset_rows, generate  # noqa: E402


class ClickHouse:
    def __init__(self, url: str, user: str, password: str):
        self.url = url.rstrip("/")
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}"}

    def execute(self, query: str, body: bytes | None = None) -> str:
        if body is None:
            url, data = self.url + "/", query.encode()
        else:
            url, data = f"{self.url}/?{urllib.parse.urlencode({'query': query})}", body
        request = urllib.request.Request(url, data=data, headers=self.headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"ClickHouse error for {query[:80]!r}: {exc.read().decode()}") from exc

    def scalar(self, query: str) -> str:
        return self.execute(query).strip()


def to_csv(rows: list[dict], fields: list[str]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def client_from_env() -> ClickHouse:
    return ClickHouse(
        os.environ.get("CLICKHOUSE_URL", "http://localhost:18123"),
        os.environ.get("CLICKHOUSE_USER", "dbt"),
        os.environ.get("CLICKHOUSE_PASSWORD", "dbt"),
    )


def load(ch: ClickHouse, seed: int, start: date, end: date) -> dict[str, int]:
    columns = ", ".join(ASSET_FIELDS)
    ch.execute(f"INSERT INTO raw.assets ({columns}) FORMAT CSVWithNames", to_csv(asset_rows(), ASSET_FIELDS))
    totals = {"days": 0, "prices": 0, "trades": 0}
    for day, (prices, trades) in generate(seed, start, end).items():
        partition = day.strftime("%Y%m%d")
        for table, rows, fields in (("prices", prices, PRICE_FIELDS), ("trades", trades, TRADE_FIELDS)):
            ch.execute(f"ALTER TABLE raw.{table} DROP PARTITION {partition}")
            if rows:
                cols = ", ".join(fields)
                ch.execute(f"INSERT INTO raw.{table} ({cols}) FORMAT CSVWithNames", to_csv(rows, fields))
            totals[table] += len(rows)
        totals["days"] += 1
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=int(os.environ.get("GENERATOR_SEED", "42")))
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=1)
    args = parser.parse_args()
    end = args.start + timedelta(days=args.days - 1)
    totals = load(client_from_env(), args.seed, args.start, end)
    print(f"loaded {totals['days']} day(s): {totals['prices']} prices, {totals['trades']} trades")


if __name__ == "__main__":
    main()
