"""Deterministic synthetic demo history (blueprint §3 augmentation policy).

- Fixed seeds -> identical data on every run (reproducible demo).
- Every row is tagged data_origin=synthetic_demo and goes through the SAME import use case
  (same validation) as the challenge workbook.
- Planted scenario for the jury (last 14 days): collection drop + e-commerce decline spike.
"""

import math
import random
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.seed.customer_fixture import assign_customers

PERIOD_START = date(2026, 5, 1)
PERIOD_END = date(2026, 11, 20)  # inclusive, matches the challenge workbook coverage
ANOMALY_START = PERIOD_END - timedelta(days=13)
DRIFT_START = ANOMALY_START - timedelta(days=7)  # planted: some regulars stop returning

CHANNELS = [("TPE / POS", 0.40), ("E-commerce", 0.25), ("Mobile App", 0.20),
            ("Contactless / NFC", 0.10), ("Bank Transfer", 0.05)]
STATUSES = [("Accepted", 0.86), ("Declined", 0.06), ("Cancelled", 0.05), ("Refunded", 0.03)]


@dataclass(frozen=True)
class DemoMerchant:
    merchant_id: str
    display_name: str
    category: str
    seed: int
    daily_mean: int
    ticket_median: float
    monthly_goal_centimes: int
    planted_anomaly: bool
    customer_seed: int | None = None  # enriched pseudonymous customer fixture (synthetic only)


HERO = DemoMerchant("M-DEMO-01", "Épicerie Démo Boumerdès", "Épicerie", 42, 12, 3200.0,
                    150_000_000, True, customer_seed=4242)
SECOND = DemoMerchant("M-DEMO-02", "Restaurant Démo", "Restauration", 43, 4, 2500.0,
                      30_000_000, False)
DEMO_MERCHANTS = (HERO, SECOND)


def _pick(rng: random.Random, weighted: list[tuple[str, float]]) -> str:
    return rng.choices([v for v, _ in weighted], weights=[w for _, w in weighted])[0]


def generate_rows(m: DemoMerchant) -> Iterator[tuple[int, dict[str, object]]]:
    rows = list(_ledger_rows(m))
    if m.customer_seed is not None:  # separate RNG: the ledger above is byte-for-byte unchanged
        assign_customers([r for _, r in rows], m.customer_seed, PERIOD_START, PERIOD_END, DRIFT_START)
    yield from rows


def customer_population(m: DemoMerchant):
    """Re-derive the fixture population (ground truth for inspection/tests; never stored)."""
    if m.customer_seed is None:
        return []
    rows = [r for _, r in _ledger_rows(m)]
    return assign_customers(rows, m.customer_seed, PERIOD_START, PERIOD_END, DRIFT_START)


def _ledger_rows(m: DemoMerchant) -> Iterator[tuple[int, dict[str, object]]]:
    rng = random.Random(m.seed)
    n, day = 0, PERIOD_START
    while day <= PERIOD_END:
        anomaly = m.planted_anomaly and day >= ANOMALY_START
        mean = m.daily_mean * (0.4 if day.weekday() == 4 else 1.0)  # Friday is quieter
        if anomaly:
            mean *= 0.55  # planted collection drop
        count = max(0, round(rng.gauss(mean, math.sqrt(mean))))
        for _ in range(count):
            n += 1
            channel = _pick(rng, CHANNELS)
            if anomaly and channel == "E-commerce":
                status = "Declined" if rng.random() < 0.40 else "Accepted"  # planted spike
            else:
                status = _pick(rng, STATUSES)
            amount = min(150_000.0, max(150.0, rng.lognormvariate(math.log(m.ticket_median), 0.7)))
            at = datetime.combine(day, datetime.min.time()) + timedelta(
                hours=rng.randint(8, 21), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
            yield n + 1, {
                "transaction_id": f"SYN-{m.merchant_id[-2:]}-{n:06d}",
                "merchant_id": m.merchant_id,
                "occurred_at": at,
                "amount": f"{amount:.2f}",
                "channel": channel,
                "status": status,
                "category": m.category,
            }
        day += timedelta(days=1)
