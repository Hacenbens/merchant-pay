"""Scenario Lab: channel-aware what-if scenarios with an exact bridge. Deterministic, NOT a forecast.

Per payment channel c, from the baseline period (initiated = all statuses):
  n_c initiated transactions, s_c = accepted / initiated, d_c = declined / initiated,
  t_c = accepted amount / accepted count (average accepted ticket)
so that n_c x s_c x t_c reproduces the channel's accepted amount exactly.

A scenario applies four levers IN THIS ORDER, and the bridge reports the change each one adds:
  1. volume     n_c -> n_c x (1 + g)                       (every channel)
  2. mix        move share k of channel A's volume to channel B (B keeps its own s and t)
  3. acceptance s_c -> s_c + da; ASSUMPTION: a gain comes only from fewer declines, so on each
                channel it is capped at that channel's observed decline share (you cannot win back
                more than you decline); capped channels are reported. A loss (da < 0) adds declines.
  4. ticket     t_c -> t_c x (1 + dt)
Each cumulative state is rounded to the centime once, and each bridge step is the difference of two
consecutive states, so the steps always add up exactly to the total change. The order matters for
how the change is attributed (stated in the UI), never for the final total.

Estimated declined value = sum n'_c x d'_c x declined ticket_c (accepted ticket when no declines).
Goal: required volume growth g* so that the scenario reaches the monthly goal pro-rated to the
baseline length (goal x days / 30): collection is linear in (1 + g), so g* = goal_p / C(g=0) - 1.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import Channel, TransactionStatus
from app.shared.domain.errors import DomainError
from app.shared.domain.money import Money

MONTH_DAYS = 30


@dataclass(frozen=True, slots=True)
class ChannelBaseline:
    channel: Channel
    initiated: int
    accepted: int
    declined: int
    accepted_amount: Money
    declined_amount: Money

    @property
    def acceptance(self) -> Decimal:
        return Decimal(self.accepted) / Decimal(self.initiated)

    @property
    def decline(self) -> Decimal:
        return Decimal(self.declined) / Decimal(self.initiated)

    @property
    def ticket_centimes(self) -> Decimal | None:  # exact, unrounded
        return Decimal(self.accepted_amount.centimes) / Decimal(self.accepted) if self.accepted else None

    @property
    def declined_ticket_centimes(self) -> Decimal | None:
        if self.declined:
            return Decimal(self.declined_amount.centimes) / Decimal(self.declined)
        return self.ticket_centimes


@dataclass(frozen=True, slots=True)
class LabBaseline:
    period: DateRange
    channels: tuple[ChannelBaseline, ...]  # only channels with activity

    @property
    def collection(self) -> Money:
        return Money.total(c.accepted_amount for c in self.channels)

    @property
    def initiated(self) -> int:
        return sum(c.initiated for c in self.channels)

    @property
    def declined_amount(self) -> Money:
        return Money.total(c.declined_amount for c in self.channels)

    def get(self, channel: Channel) -> ChannelBaseline | None:
        return next((c for c in self.channels if c.channel is channel), None)


def lab_baseline(transactions: Iterable[Transaction], period: DateRange) -> LabBaseline:
    txs = [t for t in transactions if period.contains(t.occurred_at)]
    channels = []
    for ch in Channel:
        mine = [t for t in txs if t.channel is ch]
        if not mine:
            continue
        acc = [t for t in mine if t.status is TransactionStatus.ACCEPTED]
        dec = [t for t in mine if t.status is TransactionStatus.DECLINED]
        channels.append(ChannelBaseline(ch, len(mine), len(acc), len(dec), Money.total(t.amount for t in acc),
                                        Money.total(t.amount for t in dec)))
    if not any(c.accepted for c in channels):
        raise DomainError("Baseline period has no accepted activity")
    return LabBaseline(period, tuple(channels))


@dataclass(frozen=True, slots=True)
class ChannelShift:
    from_channel: Channel
    to_channel: Channel
    share: Decimal  # fraction of the source channel's (grown) volume moved


@dataclass(frozen=True, slots=True)
class LabAssumptions:
    volume_growth: Decimal = Decimal(0)
    acceptance_change: Decimal = Decimal(0)  # absolute points (0.02 = +2 points)
    ticket_change: Decimal = Decimal(0)  # relative
    shifts: tuple[ChannelShift, ...] = ()

    def __post_init__(self) -> None:
        if not Decimal(-1) <= self.volume_growth <= Decimal(10):
            raise DomainError("volume_growth must be between -100% and +1000%")
        if not Decimal(-1) < self.ticket_change <= Decimal(10):
            raise DomainError("ticket_change must be between -100% and +1000%")
        if not Decimal(-1) <= self.acceptance_change <= Decimal(1):
            raise DomainError("acceptance_change must be between -100 and +100 points")
        out: dict[Channel, Decimal] = {}
        for s in self.shifts:
            if s.from_channel is s.to_channel:
                raise DomainError("a channel shift needs two different channels")
            if not Decimal(0) < s.share <= Decimal(1):
                raise DomainError("shift share must be between 0% and 100%")
            out[s.from_channel] = out.get(s.from_channel, Decimal(0)) + s.share
        if any(v > 1 for v in out.values()):
            raise DomainError("cannot move more than 100% of a channel's volume")


class BridgeStep(StrEnum):
    VOLUME = "volume"
    MIX = "mix"
    ACCEPTANCE = "acceptance"
    TICKET = "ticket"


@dataclass(frozen=True, slots=True)
class _State:  # per channel: (volume, acceptance, decline, ticket centimes, declined ticket centimes)
    rows: dict[Channel, tuple[Decimal, Decimal, Decimal, Decimal, Decimal]]

    def collection(self) -> Money:
        total = sum((n * s * t for n, s, _, t, _ in self.rows.values()), Decimal(0))
        return Money(int(total.quantize(Decimal(1), rounding=ROUND_HALF_UP)))

    def declined(self) -> Money:
        total = sum((n * d * dt for n, _, d, _, dt in self.rows.values()), Decimal(0))
        return Money(int(total.quantize(Decimal(1), rounding=ROUND_HALF_UP)))


@dataclass(frozen=True, slots=True)
class ChannelProjection:
    channel: Channel
    volume: Decimal
    acceptance: Decimal
    ticket: Money
    collection: Money
    declined_value: Money


@dataclass(frozen=True, slots=True)
class LabProjection:
    assumptions: LabAssumptions
    transactions: int  # rounded for display
    accepted: Decimal
    collection: Money
    delta: Money
    delta_pct: Decimal | None
    declined_value: Money
    bridge: list[tuple[BridgeStep, Money]]
    channels: list[ChannelProjection]
    required_volume_growth: Decimal | None  # to reach the pro-rated goal; None without a goal
    acceptance_capped: list[Channel]  # channels whose gain was capped at their decline share


def _start(b: LabBaseline) -> _State:
    rows = {}
    for c in b.channels:
        if c.ticket_centimes is None:  # no accepted sale: contributes 0 collection, keeps its declines
            rows[c.channel] = (Decimal(c.initiated), Decimal(0), c.decline, Decimal(0),
                               c.declined_ticket_centimes or Decimal(0))
        else:
            rows[c.channel] = (Decimal(c.initiated), c.acceptance, c.decline, c.ticket_centimes,
                               c.declined_ticket_centimes)
    return _State(rows)


def _volume(st: _State, g: Decimal) -> _State:
    return _State({ch: (n * (1 + g), s, d, t, dt) for ch, (n, s, d, t, dt) in st.rows.items()})


def _mix(st: _State, b: LabBaseline, shifts: tuple[ChannelShift, ...]) -> _State:
    rows = dict(st.rows)
    for sh in shifts:
        if sh.from_channel not in rows:
            raise DomainError(f"no baseline activity on {sh.from_channel.value} to move")
        target = b.get(sh.to_channel)
        if target is None or not target.accepted:
            raise DomainError(f"no accepted baseline on {sh.to_channel.value}: "
                              "its acceptance and ticket are unknown")
        moved = st.rows[sh.from_channel][0] * sh.share  # share of the grown volume, before other shifts
        n, s, d, t, dt = rows[sh.from_channel]
        rows[sh.from_channel] = (n - moved, s, d, t, dt)
        n, s, d, t, dt = rows[sh.to_channel]
        rows[sh.to_channel] = (n + moved, s, d, t, dt)
    return _State(rows)


def _acceptance(st: _State, da: Decimal) -> tuple[_State, list[Channel]]:
    rows, capped = {}, []
    for ch, (n, s, d, t, dt) in st.rows.items():
        if t == 0:  # channel without accepted baseline: acceptance lever not applicable
            rows[ch] = (n, s, d, t, dt)
            continue
        change = da
        if da > d:  # cannot recover more than the declines this channel actually has
            change, capped = d, [*capped, ch]
        elif -da > s:
            raise DomainError(f"acceptance on {ch.value} would fall below 0%")
        rows[ch] = (n, s + change, d - change, t, dt)
    return _State(rows), capped


def _ticket(st: _State, dt_change: Decimal) -> _State:
    return _State({ch: (n, s, d, t * (1 + dt_change), dt) for ch, (n, s, d, t, dt) in st.rows.items()})


def project(b: LabBaseline, a: LabAssumptions, goal_for_period: Money | None = None) -> LabProjection:
    s0 = _start(b)
    s1 = _volume(s0, a.volume_growth)
    s2 = _mix(s1, b, a.shifts)
    s3, capped = _acceptance(s2, a.acceptance_change)
    s4 = _ticket(s3, a.ticket_change)
    c = [s.collection() for s in (s0, s1, s2, s3, s4)]
    bridge = [(step, c[i + 1] - c[i]) for i, step in enumerate(BridgeStep)]
    delta = c[4] - c[0]

    required = None
    if goal_for_period is not None:
        no_growth = project(b, replace(a, volume_growth=Decimal(0))).collection
        if no_growth.centimes > 0:
            required = (Decimal(goal_for_period.centimes) / Decimal(no_growth.centimes) - 1).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP)

    channels = []
    for ch, (n, s, d, t, dt) in s4.rows.items():
        channels.append(ChannelProjection(
            ch, n, s, Money(int(t.quantize(Decimal(1), rounding=ROUND_HALF_UP))),
            _State({ch: (n, s, d, t, dt)}).collection(), _State({ch: (n, s, d, t, dt)}).declined()))
    volume = sum((n for n, *_ in s4.rows.values()), Decimal(0))
    accepted = sum((n * s for n, s, *_ in s4.rows.values()), Decimal(0))
    return LabProjection(
        assumptions=a, transactions=int(volume.quantize(Decimal(1), rounding=ROUND_HALF_UP)),
        accepted=accepted, collection=c[4], delta=delta,
        delta_pct=(Decimal(delta.centimes) / Decimal(c[0].centimes)) if c[0].centimes else None,
        declined_value=s4.declined(), bridge=bridge, channels=channels, required_volume_growth=required,
        acceptance_capped=capped,
    )


def goal_for_period(monthly_goal: Money | None, period: DateRange) -> Money | None:
    """The monthly goal pro-rated to the baseline length (a 30-day month)."""
    if monthly_goal is None:
        return None
    return monthly_goal.scale(Decimal(period.days) / Decimal(MONTH_DAYS))
