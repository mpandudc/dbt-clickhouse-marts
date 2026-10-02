"""Deterministic multi-asset trade and price generator.

Every day is derived from a walk that starts at EPOCH, so the rows for a given
date are identical no matter which date range is requested. That property is
what makes per-day backfills idempotent.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal
from pathlib import Path

EPOCH = date(2026, 1, 1)
ACCOUNTS = ("acc-001", "acc-002", "acc-003", "acc-004", "acc-005")


@dataclass(frozen=True)
class Asset:
    asset_id: str
    symbol: str
    asset_class: str
    quote_ccy: str
    lot_size: Decimal
    start_price: Decimal
    daily_vol: float
    price_scale: int


ASSETS = (
    Asset("crypto:btc", "btc", "crypto", "USDT", Decimal("0.0001"), Decimal("95000"), 0.030, 2),
    Asset("crypto:eth", "eth", "crypto", "USDT", Decimal("0.001"), Decimal("3300"), 0.040, 2),
    Asset("crypto:sol", "sol", "crypto", "USDT", Decimal("0.01"), Decimal("190"), 0.055, 3),
    Asset("idx:bbca", "bbca", "idx_equity", "IDR", Decimal("100"), Decimal("9800"), 0.015, 0),
    Asset("idx:bbri", "bbri", "idx_equity", "IDR", Decimal("100"), Decimal("4300"), 0.020, 0),
    Asset("idx:tlkm", "tlkm", "idx_equity", "IDR", Decimal("100"), Decimal("2800"), 0.018, 0),
)

FEE_RATE = {"crypto": Decimal("0.001"), "idx_equity": Decimal("0.0015")}
# Cash budget per trade, expressed in each asset's quote currency.
TICKET = {"USDT": (Decimal("200"), Decimal("5000")), "IDR": (Decimal("2000000"), Decimal("50000000"))}


def trades_open(asset: Asset, day: date) -> bool:
    return asset.asset_class == "crypto" or day.weekday() < 5


def day_rng(seed: int, day: date, salt: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}|{day.isoformat()}|{salt}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def quantize_down(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S.000")


class Market:
    def __init__(self, seed: int):
        self.seed = seed
        self.day = EPOCH - timedelta(days=1)
        self.prices = {a.asset_id: a.start_price for a in ASSETS}
        self.holdings = {(acc, a.asset_id): Decimal(0) for acc in ACCOUNTS for a in ASSETS}
        self.trade_seq = 0

    def step(self) -> tuple[date, list[dict], list[dict]]:
        self.day += timedelta(days=1)
        day = self.day
        prices: list[dict] = []
        for asset in ASSETS:
            if not trades_open(asset, day):
                continue
            rng = day_rng(self.seed, day, f"px:{asset.asset_id}")
            shock = rng.gauss(0, asset.daily_vol) - 0.5 * asset.daily_vol**2
            new_price = Decimal(str(float(self.prices[asset.asset_id]) * math.exp(shock)))
            step = Decimal(1).scaleb(-asset.price_scale)
            self.prices[asset.asset_id] = new_price.quantize(step, rounding=ROUND_HALF_EVEN)
            prices.append(
                {"price_date": day.isoformat(), "asset_id": asset.asset_id, "close": str(self.prices[asset.asset_id])}
            )

        trades: list[dict] = []
        rng = day_rng(self.seed, day, "trades")
        open_assets = [a for a in ASSETS if trades_open(a, day)]
        for _ in range(rng.randint(25, 45)):
            asset = rng.choice(open_assets)
            account = rng.choice(ACCOUNTS)
            key = (account, asset.asset_id)
            mark = self.prices[asset.asset_id]
            # Intraday fill within +/-1% of the close.
            fill = (mark * Decimal(str(1 + rng.uniform(-0.01, 0.01)))).quantize(
                Decimal(1).scaleb(-asset.price_scale), rounding=ROUND_HALF_EVEN
            )
            held = self.holdings[key]
            side = "buy" if held == 0 or rng.random() < 0.6 else "sell"
            if side == "buy":
                low, high = TICKET[asset.quote_ccy]
                budget = low + (high - low) * Decimal(str(rng.random()))
                qty = quantize_down(budget / fill, asset.lot_size)
            else:
                qty = quantize_down(held * Decimal(str(rng.uniform(0.2, 1.0))), asset.lot_size)
            if qty <= 0:
                continue
            fee = (qty * fill * FEE_RATE[asset.asset_class]).quantize(Decimal("0.00000001"))
            self.holdings[key] = held + qty if side == "buy" else held - qty
            self.trade_seq += 1
            seconds = rng.randint(0, 86_399) if asset.asset_class == "crypto" else rng.randint(2 * 3600, 9 * 3600)
            executed_at = datetime.combine(day, time(), tzinfo=UTC) + timedelta(seconds=seconds)
            row = {
                "trade_id": f"t-{day:%Y%m%d}-{self.trade_seq:06d}",
                "account_id": account,
                # Upstream sends inconsistent casing; staging normalises it.
                "asset_id": asset.asset_id if rng.random() > 0.1 else asset.asset_id.upper(),
                "side": side if rng.random() > 0.1 else side.upper(),
                "quantity": str(qty),
                "price": str(fill),
                "fee": str(fee),
                "executed_at": ts(executed_at),
                "trade_date": day.isoformat(),
                "ingested_at": ts(executed_at + timedelta(seconds=rng.randint(1, 30))),
            }
            trades.append(row)
            # At-least-once upstream: ~2% of trades are re-delivered later.
            if rng.random() < 0.02:
                trades.append({**row, "ingested_at": ts(executed_at + timedelta(minutes=rng.randint(5, 90)))})
        return day, prices, trades


def generate(seed: int, start: date, end: date) -> dict[date, tuple[list[dict], list[dict]]]:
    if start < EPOCH:
        raise ValueError(f"start must be on or after {EPOCH}")
    if end < start:
        raise ValueError("end must not be before start")
    market = Market(seed)
    out: dict[date, tuple[list[dict], list[dict]]] = {}
    while market.day < end:
        day, prices, trades = market.step()
        if day >= start:
            out[day] = (prices, trades)
    return out


def asset_rows() -> list[dict]:
    return [
        {
            "asset_id": a.asset_id,
            "symbol": a.symbol,
            "asset_class": a.asset_class,
            "quote_ccy": a.quote_ccy,
            "lot_size": str(a.lot_size),
        }
        for a in ASSETS
    ]


TRADE_FIELDS = [
    "trade_id", "account_id", "asset_id", "side", "quantity", "price", "fee",
    "executed_at", "trade_date", "ingested_at",
]
PRICE_FIELDS = ["price_date", "asset_id", "close"]
ASSET_FIELDS = ["asset_id", "symbol", "asset_class", "quote_ccy", "lot_size"]


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start", type=date.fromisoformat, default=EPOCH)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--out", type=Path, default=Path("data"))
    args = parser.parse_args()
    end = args.start + timedelta(days=args.days - 1)
    for day, (prices, trades) in generate(args.seed, args.start, end).items():
        write_csv(args.out / f"prices/{day}.csv", prices, PRICE_FIELDS)
        write_csv(args.out / f"trades/{day}.csv", trades, TRADE_FIELDS)
    write_csv(args.out / "assets.csv", asset_rows(), ASSET_FIELDS)
    print(f"wrote {args.days} day(s) to {args.out}")


if __name__ == "__main__":
    main()
