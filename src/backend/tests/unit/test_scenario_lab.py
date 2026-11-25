"""Scenario Lab: exact reconciliation, bridge sums, channel mix, acceptance cap, goal solver."""

from datetime import date
from decimal import Decimal as D

import pytest

from app.contexts.analytics.domain.kpis import compute_kpis
from app.contexts.simulation.domain.growth import Assumptions, Baseline, simulate
from app.contexts.simulation.domain.scenario_lab import (
    BridgeStep,
    ChannelShift,
    LabAssumptions,
    goal_for_period,
    lab_baseline,
    project,
)
from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import Channel
from app.shared.domain.errors import DomainError
from app.shared.domain.money import Money
from tests.factories import A, C, tx
from tests.factories import D as DEC

PERIOD = DateRange.inclusive(date(2026, 11, 1), date(2026, 11, 30))  # 30 days
POS, ECOM, BANK = Channel.POS, Channel.ECOMMERCE, Channel.BANK_TRANSFER


def ledger():
    """POS: 10 attempts, 9 accepted x 1000, 1 declined x 500. E-com: 10 attempts, 6 x 500, 4 declined."""
    rows = [tx(f"P{i}", A, "1000.00", channel=POS) for i in range(9)] + [tx("PD", DEC, "500.00", channel=POS)]
    rows += [tx(f"E{i}", A, "500.00", channel=ECOM) for i in range(6)]
    rows += [tx(f"ED{i}", DEC, "800.00", channel=ECOM) for i in range(4)]
    rows += [tx("BX", C, "100.00", channel=BANK)]  # bank: one cancelled, nothing accepted
    return rows


def test_baseline_reconciles_with_the_ledger():
    b = lab_baseline(ledger(), PERIOD)
    assert b.collection == Money.of("12000.00") and b.initiated == 21
    pos = b.get(POS)
    assert (pos.initiated, pos.accepted, pos.declined) == (10, 9, 1) and pos.acceptance == D("0.9")
    nothing = project(b, LabAssumptions())
    assert nothing.collection == b.collection and nothing.delta == Money(0)
    assert nothing.declined_value == Money.of("3700.00")  # 500 + 4 x 800


def test_volume_only_matches_the_existing_growth_simulator():
    b = lab_baseline(ledger(), PERIOD)
    lab = project(b, LabAssumptions(volume_growth=D("0.15")))
    legacy = simulate(Baseline.from_kpis(compute_kpis(ledger())), Assumptions(volume_growth=D("0.15")))
    assert lab.collection == legacy.projected_collection == Money.of("13800.00")
    assert lab.bridge[0] == (BridgeStep.VOLUME, Money.of("1800.00"))


def test_mix_shift_uses_each_channels_own_acceptance_and_ticket():
    b = lab_baseline(ledger(), PERIOD)
    r = project(b, LabAssumptions(shifts=(ChannelShift(ECOM, POS, D("0.5")),)))
    # 5 e-com attempts move to POS: lose 5 x 0.6 x 500 = 1500, gain 5 x 0.9 x 1000 = 4500
    assert dict(r.bridge)[BridgeStep.MIX] == Money.of("3000.00") and r.collection == Money.of("15000.00")
    assert r.transactions == 21  # a shift moves volume, it does not create it


def test_acceptance_gain_is_capped_by_declines_and_bridge_is_exact():
    b = lab_baseline(ledger(), PERIOD)
    a = LabAssumptions(D("0.10"), D("0.20"), D("0.05"), (ChannelShift(ECOM, POS, D("0.3")),))
    r = project(b, a)
    assert sum(m.centimes for _, m in r.bridge) == r.delta.centimes
    assert [s for s, _ in r.bridge] == [
        BridgeStep.VOLUME,
        BridgeStep.MIX,
        BridgeStep.ACCEPTANCE,
        BridgeStep.TICKET,
    ]
    assert r.acceptance_capped == [POS]  # POS declines only 10 %: +20 points capped at +10
    pos = next(c for c in r.channels if c.channel is POS)
    assert pos.acceptance == D("1.0") and pos.declined_value == Money(0)
    with pytest.raises(DomainError):
        project(b, LabAssumptions(acceptance_change=D("-0.95")))


def test_shift_validation():
    b = lab_baseline(ledger(), PERIOD)
    with pytest.raises(DomainError):  # bank has no accepted baseline: its ticket is unknown
        project(b, LabAssumptions(shifts=(ChannelShift(POS, BANK, D("0.1")),)))
    with pytest.raises(DomainError):
        LabAssumptions(shifts=(ChannelShift(POS, POS, D("0.1")),))
    with pytest.raises(DomainError):
        LabAssumptions(shifts=(ChannelShift(POS, ECOM, D("0.7")), ChannelShift(POS, BANK, D("0.4"))))
    with pytest.raises(DomainError):
        lab_baseline([tx("BX", C, "100.00", channel=BANK)], PERIOD)


def test_goal_solver_is_linear_in_volume():
    b = lab_baseline(ledger(), PERIOD)
    goal = goal_for_period(Money.of("18000.00"), PERIOD)  # 30-day period: the full goal
    assert goal == Money.of("18000.00")
    r = project(b, LabAssumptions(ticket_change=D("0.20")), goal)  # 12,000 x 1.2 = 14,400 at g = 0
    assert r.required_volume_growth == D("0.2500")  # 18,000 / 14,400 - 1
    assert project(b, LabAssumptions(), None).required_volume_growth is None
    assert goal_for_period(
        Money.of("3000.00"), DateRange.inclusive(date(2026, 11, 1), date(2026, 11, 10))
    ) == Money.of("1000.00")
