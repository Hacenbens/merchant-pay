"""Synthetic, pseudonymous customer-activity fixture for the demo merchant (NOT challenge data).

The official 7-field schema has no customer identifier, so customer analytics cannot be built from it.
This module enriches the *synthetic* demo ledger only: it assigns a random, merchant-scoped
`customer_token` to existing generated transactions, without changing any amount, date, channel or
status, so every merchant-level KPI, alert and runbook figure stays identical.

Behaviour model (fixed seed, reproducible):
- regulars return every ~5-9 days, occasionals every ~18-40 days, both joining over time (cohorts);
- a small per-visit chance of leaving for good produces naturally lapsed customers;
- one-time customers appear when no known customer is due;
- PLANTED: a group of regulars stops returning from DRIFT_START (the win-back story);
- ~15% of transactions stay untokenised (walk-ins outside the programme).

Ground truth (archetype, planted drift) is exposed by `ground_truth()` for inspection and tests only.
It is never stored in the database and never used as an input by the analytics.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from app.contexts.ledger.domain.row_parsing import parse_customer_token

TOKENISED_SHARE = 0.85
REGULARS, OCCASIONALS, DRIFTING = 45, 140, 14


@dataclass
class _Customer:
    token: str
    archetype: str  # regular | occasional | one_time
    mean_interval: float
    joined: date
    next_due: date
    left_on: date | None = None
    planted_drift: bool = False


_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"  # Crockford base32, lowercase


def _token(rng: random.Random) -> str:
    """Random (independent of any card/account data); re-drawn until the importer accepts it."""
    while True:
        token = "cus_" + "".join(rng.choice(_ALPHABET) for _ in range(16))
        try:
            parse_customer_token(token)
            return token
        except ValueError:
            continue


def _population(seed: int, start: date, end: date,
                drift_start: date) -> tuple[random.Random, list[_Customer]]:
    rng = random.Random(seed)
    span = (end - start).days
    people: list[_Customer] = []
    for archetype, n, lo, hi in (("regular", REGULARS, 5, 9), ("occasional", OCCASIONALS, 18, 40)):
        for _ in range(n):
            joined = start if rng.random() < 0.6 else start + timedelta(days=rng.randrange(span - 30))
            mean = rng.uniform(lo, hi)
            people.append(_Customer(_token(rng), archetype, mean, joined,
                                    joined + timedelta(days=rng.randrange(int(mean) + 1))))
    early_regulars = [c for c in people if c.archetype == "regular" and c.joined <= start + timedelta(60)]
    for c in rng.sample(early_regulars, DRIFTING):
        c.planted_drift, c.left_on = True, drift_start
    return rng, people


def assign_customers(rows: list[dict[str, object]], seed: int, start: date, end: date,
                     drift_start: date) -> list[_Customer]:
    """Mutates rows in place (adds customer_token or leaves it absent). Returns the population."""
    rng, people = _population(seed, start, end, drift_start)
    for row in sorted(rows, key=lambda r: r["occurred_at"]):
        day = row["occurred_at"].date()
        if rng.random() >= TOKENISED_SHARE:
            continue
        active = [c for c in people if c.joined <= day and (c.left_on is None or day < c.left_on)]
        due = [c for c in active if c.next_due <= day]
        if due:
            weights = [(day - c.next_due).days + 1 for c in due]
            c = rng.choices(due, weights=weights)[0]
        elif active and rng.random() < 0.5:
            c = min(active, key=lambda x: x.next_due)  # an early return
        else:
            c = _Customer(_token(rng), "one_time", 0, day, date.max)
            people.append(c)
        row["customer_token"] = c.token
        if c.archetype == "one_time":
            c.left_on = day + timedelta(days=1)
            continue
        c.next_due = day + timedelta(days=max(1, round(rng.gauss(c.mean_interval, c.mean_interval * 0.3))))
        if rng.random() < (0.004 if c.archetype == "regular" else 0.02):
            c.left_on = day + timedelta(days=1)  # natural, unplanned lapse
    return people


def ground_truth(people: list[_Customer]) -> dict[str, dict[str, object]]:
    return {c.token: {"archetype": c.archetype, "planted_drift": c.planted_drift} for c in people}
