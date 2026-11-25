"""Points ledger: immutable, idempotent entries. A balance is always a SUM, never a stored number.

Pilot accrual replays historical accepted, tokenised transactions under one programme version:
no points are issued to real customers. Each entry has an idempotency key, unique per merchant:
  earn:v{version}:{transaction_id}     one earn per transaction and version (re-runs, re-imports
                                        and retries cannot double-reward)
  expire:v{version}:{transaction_id}   the unredeemed remainder of that earn, once expiry_days pass
Caps: a customer earns at most cap_points_per_customer under one version (later earns are cut).
Refunds: the data does not link a refund to its original sale, so refunds NEVER reverse points
here. A reversal would require a reliable original_transaction_id (not present).
Redemptions do not exist in the data; the simulator models them as an assumption instead.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from app.contexts.ledger.domain.transaction import Transaction
from app.contexts.loyalty.domain.program import ProgramVersion, eligible
from app.shared.domain.money import Money


class EntryKind(StrEnum):
    EARN = "earn"
    EXPIRE = "expire"
    REDEEM = "redeem"  # reserved: no redemption events exist in the data
    REVERSE = "reverse"  # reserved: needs a reliable refund-to-sale link
    ADJUST = "adjust"  # reserved for manual corrections


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    customer_token: str
    kind: EntryKind
    points: int  # signed: earn > 0, expire/redeem/reverse < 0
    occurred_on: date
    idempotency_key: str
    program_version: int
    source_transaction_id: str | None = None


def earn_key(version: int, transaction_id: str) -> str:
    return f"earn:v{version}:{transaction_id}"


def expire_key(version: int, transaction_id: str) -> str:
    return f"expire:v{version}:{transaction_id}"


def plan_accrual(program: ProgramVersion, transactions: Iterable[Transaction],
                 existing: Iterable[LedgerEntry], today: date) -> list[LedgerEntry]:
    """New entries only. Existing keys are skipped, so running it twice adds nothing the 2nd time."""
    rules, v = program.rules, program.version
    prior = [e for e in existing if e.program_version == v]
    keys = {e.idempotency_key for e in prior}
    earned: dict[str, int] = defaultdict(int)
    for e in prior:
        if e.kind is EntryKind.EARN:
            earned[e.customer_token] += e.points

    new: list[LedgerEntry] = []
    txs = sorted((t for t in eligible(transactions)
                  if program.effective_from <= t.occurred_at.date() <= today),
                 key=lambda t: (t.occurred_at, t.transaction_id))
    for t in txs:
        key = earn_key(v, t.transaction_id)
        if key in keys:
            continue
        points = rules.points_for(t.amount)
        if rules.cap_points_per_customer is not None:
            points = min(points, rules.cap_points_per_customer - earned[t.customer_token])
        if points <= 0:
            continue
        earned[t.customer_token] += points
        new.append(LedgerEntry(t.customer_token, EntryKind.EARN, points, t.occurred_at.date(), key, v,
                               t.transaction_id))

    if rules.expiry_days is not None:
        for e in [*prior, *new]:
            if e.kind is not EntryKind.EARN:
                continue
            due = e.occurred_on + timedelta(days=rules.expiry_days)
            key = expire_key(v, e.source_transaction_id)
            if due <= today and key not in keys:
                new.append(LedgerEntry(e.customer_token, EntryKind.EXPIRE, -e.points, due, key, v,
                                       e.source_transaction_id))
    return new


@dataclass(frozen=True, slots=True)
class LedgerSummary:
    program_version: int
    earned: int
    expired: int
    outstanding: int  # points still redeemable
    customers_with_balance: int
    liability: Money  # outstanding x point value (face value, before any redemption assumption)
    budget: Money | None
    liability_over_budget: Money | None


def summarise(program: ProgramVersion, entries: Iterable[LedgerEntry]) -> LedgerSummary:
    mine = [e for e in entries if e.program_version == program.version]
    balance: dict[str, int] = defaultdict(int)
    for e in mine:
        balance[e.customer_token] += e.points
    if any(b < 0 for b in balance.values()):
        raise ValueError("ledger integrity: a customer balance is negative")
    outstanding = sum(balance.values())
    liability = program.rules.point_value.scale(outstanding)
    budget = program.rules.campaign_budget
    over = (liability - budget) if budget and liability.centimes > budget.centimes else None
    return LedgerSummary(
        program.version,
        earned=sum(e.points for e in mine if e.kind is EntryKind.EARN),
        expired=-sum(e.points for e in mine if e.kind is EntryKind.EXPIRE),
        outstanding=outstanding,
        customers_with_balance=sum(1 for b in balance.values() if b > 0),
        liability=liability, budget=budget, liability_over_budget=over,
    )
