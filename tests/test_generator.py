import sys
import unittest
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generator"))

from generate import ASSETS, EPOCH, generate  # noqa: E402

IDX = {a.asset_id for a in ASSETS if a.asset_class == "idx_equity"}


class GeneratorTest(unittest.TestCase):
    def test_day_is_independent_of_requested_range(self):
        day = date(2026, 1, 20)
        alone = generate(42, day, day)[day]
        in_range = generate(42, EPOCH, day + timedelta(days=5))[day]
        self.assertEqual(alone, in_range)

    def test_seed_changes_output(self):
        day = date(2026, 1, 5)
        self.assertNotEqual(generate(1, day, day)[day], generate(2, day, day)[day])

    def test_no_idx_activity_on_weekends(self):
        days = generate(42, EPOCH, date(2026, 1, 31))
        for day, (prices, trades) in days.items():
            if day.weekday() >= 5:
                self.assertFalse({p["asset_id"] for p in prices} & IDX, day)
                self.assertFalse({t["asset_id"].lower() for t in trades} & IDX, day)

    def test_spot_positions_never_go_negative(self):
        holdings: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        seen: set[str] = set()
        for _, (_, trades) in sorted(generate(42, EPOCH, date(2026, 2, 28)).items()):
            for trade in trades:
                if trade["trade_id"] in seen:
                    continue  # re-delivery
                seen.add(trade["trade_id"])
                key = (trade["account_id"], trade["asset_id"].lower())
                qty = Decimal(trade["quantity"])
                holdings[key] += qty if trade["side"].lower() == "buy" else -qty
                self.assertGreaterEqual(holdings[key], 0, trade)

    def test_redeliveries_are_exact_copies_with_later_ingestion(self):
        by_id: dict[str, list[dict]] = defaultdict(list)
        for (_, trades) in generate(42, EPOCH, date(2026, 2, 28)).values():
            for trade in trades:
                by_id[trade["trade_id"]].append(trade)
        duplicates = [rows for rows in by_id.values() if len(rows) > 1]
        self.assertTrue(duplicates, "expected at least one re-delivery in two months")
        for first, again in duplicates:
            self.assertEqual({k: v for k, v in first.items() if k != "ingested_at"},
                             {k: v for k, v in again.items() if k != "ingested_at"})
            self.assertGreater(again["ingested_at"], first["ingested_at"])

    def test_rejects_dates_before_epoch(self):
        with self.assertRaises(ValueError):
            generate(42, EPOCH - timedelta(days=1), EPOCH)


if __name__ == "__main__":
    unittest.main()
