"""Customer insight use cases. Every read derives from the scoped ledger; nothing is cached."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Protocol

from app.contexts.customers.domain.profiles import (
    CustomerBook,
    CustomerProfile,
    GroupTotal,
    MonthActivity,
    NewVsReturning,
    Segment,
    SegmentRules,
    build_book,
    by_segment,
    by_status,
    mask,
    monthly_activity,
    new_vs_returning,
    repeat_rate,
)
from app.contexts.customers.domain.reengagement import (
    Decision,
    MerchantDecision,
    ReengageEntry,
    reengagement_list,
    validate_decision,
)
from app.contexts.customers.domain.winback import ReturnStatus
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import TransactionStatus
from app.shared.domain.errors import DomainError, NotFound
from app.shared.domain.merchant_scope import MerchantScope
from app.shared.domain.money import Money
from app.shared.domain.rate import Rate

HISTORY_START = date(2000, 1, 1)
MIN_WINDOW_DAYS, MAX_WINDOW_DAYS = 30, 365


class TransactionReader(Protocol):
    def list_in_period(self, scope: MerchantScope, period: DateRange) -> list[Transaction]: ...


class DecisionRepository(Protocol):
    def latest(self, scope: MerchantScope) -> dict[str, MerchantDecision]: ...

    def add(self, scope: MerchantScope, token: str, decision: Decision,
            snooze_until: date | None) -> MerchantDecision: ...


class AuditLog(Protocol):
    def record(self, actor_id: int, action: str, entity_ref: str) -> None: ...


def rules_for(window_days: int) -> SegmentRules:
    if not MIN_WINDOW_DAYS <= window_days <= MAX_WINDOW_DAYS:
        raise DomainError(f"window_days must be between {MIN_WINDOW_DAYS} and {MAX_WINDOW_DAYS}")
    return replace(SegmentRules(), window_days=window_days)


class _Base:
    def __init__(self, reader: TransactionReader) -> None:
        self._reader = reader

    def _history(self, scope: MerchantScope, as_of: date) -> list[Transaction]:
        return self._reader.list_in_period(scope, DateRange(HISTORY_START, as_of + timedelta(days=1)))


@dataclass(frozen=True, slots=True)
class CustomerOverview:
    book: CustomerBook
    repeat_rate: Rate
    segments: dict[Segment, GroupTotal]
    statuses: dict[ReturnStatus, GroupTotal]
    new_vs_returning: NewVsReturning
    monthly: list[MonthActivity]


class GetCustomerOverview(_Base):
    def execute(self, scope: MerchantScope, as_of: date, window_days: int,
                period: DateRange) -> CustomerOverview:
        history = self._history(scope, as_of)
        book = build_book(history, as_of, rules_for(window_days))
        return CustomerOverview(book, repeat_rate(book), by_segment(book), by_status(book),
                                new_vs_returning(history, period), monthly_activity(history, book))


@dataclass(frozen=True, slots=True)
class CustomerPage:
    book: CustomerBook
    items: list[CustomerProfile]
    total: int
    page: int
    size: int


class ListCustomers(_Base):
    def execute(self, scope: MerchantScope, as_of: date, window_days: int, *,
                segment: Segment | None = None, status: ReturnStatus | None = None,
                high_value: bool | None = None, page: int = 1, size: int = 25) -> CustomerPage:
        book = build_book(self._history(scope, as_of), as_of, rules_for(window_days))
        rows = [p for p in book.profiles
                if (segment is None or p.segment is segment)
                and (status is None or p.evidence.status is status)
                and (high_value is None or p.high_value is high_value)]
        rows.sort(key=lambda p: (-p.monetary.centimes, p.token))
        start = (page - 1) * size
        return CustomerPage(book, rows[start:start + size], len(rows), page, size)


@dataclass(frozen=True, slots=True)
class StatusCount:
    status: TransactionStatus
    count: int
    amount: Money


@dataclass(frozen=True, slots=True)
class CustomerDetail:
    book: CustomerBook
    profile: CustomerProfile
    recent: list[Transaction]  # this customer's transactions (all statuses), newest first
    statuses: list[StatusCount]
    decision: MerchantDecision | None


class GetCustomer(_Base):
    RECENT = 30

    def __init__(self, reader: TransactionReader, decisions: DecisionRepository) -> None:
        super().__init__(reader)
        self._decisions = decisions

    def execute(self, scope: MerchantScope, as_of: date, window_days: int, token: str) -> CustomerDetail:
        history = self._history(scope, as_of)
        book = build_book(history, as_of, rules_for(window_days))
        profile = next((p for p in book.profiles if p.token == token), None)
        if profile is None:  # unknown, outside the window, or another merchant's: same answer
            raise NotFound("Customer not found")
        mine = sorted((t for t in history if t.customer_token == token),
                      key=lambda t: t.occurred_at, reverse=True)
        statuses = [StatusCount(s, sum(1 for t in mine if t.status is s),
                                Money.total(t.amount for t in mine if t.status is s))
                    for s in TransactionStatus]
        return CustomerDetail(book, profile, mine[:self.RECENT], statuses,
                              self._decisions.latest(scope).get(token))


@dataclass(frozen=True, slots=True)
class Reengagement:
    book: CustomerBook
    entries: list[ReengageEntry]
    hidden_count: int


class GetReengagement(_Base):
    def __init__(self, reader: TransactionReader, decisions: DecisionRepository) -> None:
        super().__init__(reader)
        self._decisions = decisions

    def execute(self, scope: MerchantScope, as_of: date, window_days: int,
                include_hidden: bool = False) -> Reengagement:
        book = build_book(self._history(scope, as_of), as_of, rules_for(window_days))
        all_entries = reengagement_list(book, self._decisions.latest(scope), as_of, include_hidden=True)
        visible = all_entries if include_hidden else [e for e in all_entries if not e.hidden]
        return Reengagement(book, visible, sum(1 for e in all_entries if e.hidden))


class RecordDecision(_Base):
    """The merchant's own choice on a suggestion. Audited with a masked token; nothing is sent."""

    def __init__(self, reader: TransactionReader, decisions: DecisionRepository, audit: AuditLog) -> None:
        super().__init__(reader)
        self._decisions, self._audit = decisions, audit

    def execute(self, scope: MerchantScope, token: str, decision: Decision,
                snooze_until: date | None, today: date) -> MerchantDecision:
        validate_decision(decision, snooze_until, today)
        if not any(t.customer_token == token for t in self._history(scope, today)):
            raise NotFound("Customer not found")
        saved = self._decisions.add(scope, token, decision, snooze_until)
        self._audit.record(scope.user_id, "customer.decision",
                           f"merchant:{scope.merchant_id} customer:{mask(token)} decision:{decision.value}")
        return saved
