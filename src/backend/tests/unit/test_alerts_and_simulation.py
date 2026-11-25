from datetime import date
from decimal import Decimal

import pytest

from app.contexts.alerts.domain.alert import AlertState, Severity
from app.contexts.alerts.domain.rules import (
    CollectionDropRule,
    DeclineSpikeRule,
    GoalReachedRule,
    InactivityRule,
    RuleContext,
)
from app.contexts.analytics.domain.kpis import compute_kpis
from app.contexts.simulation.domain.growth import Assumptions, Baseline, simulate
from app.shared.domain.date_range import DateRange
from app.shared.domain.errors import DomainError, InvalidStateTransition
from app.shared.domain.money import Money
from tests.factories import A, D, tx

CUR = DateRange.inclusive(date(2026, 11, 7), date(2026, 11, 20))


def _ctx(current, previous):
    return RuleContext("M1", date(2026, 11, 20), CUR, CUR.previous(), current, previous)


def test_collection_drop_fires_at_20_percent_with_explanation():
    previous = [tx(f"p{i}", A, "1000", "2026-10-30 10:00") for i in range(10)]
    current = [tx(f"c{i}", A, "1000") for i in range(8)]
    alert = CollectionDropRule().evaluate(_ctx(current, previous))
    assert alert is not None and alert.delta_pct == Decimal("-0.2")
    assert "10000.00" in alert.explanation and "8000.00" in alert.explanation


def test_collection_drop_quiet_on_small_samples():
    previous = [tx(f"p{i}", A, "1000", "2026-10-30 10:00") for i in range(3)]
    assert CollectionDropRule().evaluate(_ctx([], previous)) is None


def test_decline_spike_shows_denominator_and_baseline():
    previous = [tx(f"p{i}", A, "1000", "2026-10-30 10:00") for i in range(17)] + [
        tx(f"pd{i}", D, "1000", "2026-10-30 11:00") for i in range(3)]
    current = [tx(f"c{i}", A, "1000") for i in range(10)] + [
        tx(f"cd{i}", D, "1000") for i in range(10)]
    alert = DeclineSpikeRule().evaluate(_ctx(current, previous))
    assert alert is not None
    assert alert.observed_value == Decimal("0.5") and alert.baseline_value == Decimal("0.15")
    assert "10 / 20" in alert.explanation and "3 / 20" in alert.explanation
    assert alert.severity is Severity.CRITICAL


def test_decline_spike_respects_minimum_sample():
    previous = [tx(f"p{i}", A, "1000", "2026-10-30 10:00") for i in range(10)]
    current = [tx(f"c{i}", D, "1000") for i in range(11)]
    assert DeclineSpikeRule().evaluate(_ctx(current, previous)) is None


def test_inactivity_fires_after_three_times_the_median_gap():
    history = [tx(f"h{d}-{i}", A, "1000", f"2026-11-{d:02d} 10:00")
               for d in range(1, 7) for i in range(2)]
    alert = InactivityRule().evaluate(_ctx([], history))
    assert alert is not None and alert.observed_value == Decimal(14)  # last activity 2026-11-06
    assert alert.baseline_value == Decimal(1)
    assert alert.severity is Severity.CRITICAL


def test_goal_rule_reports_month_to_date_progress():
    ctx = RuleContext("M1", date(2026, 11, 20), CUR, CUR.previous(), [], [],
                      monthly_goal=Money.of(1000), month_to_date=[tx("g1", A, "850")])
    alert = GoalReachedRule().evaluate(ctx)
    assert alert is not None and alert.severity is Severity.INFO
    assert "85%" in alert.explanation and alert.delta_pct == Decimal("-0.15")
    assert alert.window == DateRange.inclusive(date(2026, 11, 1), date(2026, 11, 20))


def test_goal_rule_needs_a_goal_and_eighty_percent():
    no_goal = RuleContext("M1", date(2026, 11, 20), CUR, CUR.previous(), [], [],
                          month_to_date=[tx("g1", A, "850")])
    assert GoalReachedRule().evaluate(no_goal) is None
    below = RuleContext("M1", date(2026, 11, 20), CUR, CUR.previous(), [], [],
                        monthly_goal=Money.of(1000), month_to_date=[tx("g1", A, "500")])
    assert GoalReachedRule().evaluate(below) is None


def test_alert_state_machine():
    previous = [tx(f"p{i}", A, "1000", "2026-10-30 10:00") for i in range(10)]
    alert = CollectionDropRule().evaluate(_ctx([], previous))
    alert.acknowledge()
    assert alert.state is AlertState.ACKNOWLEDGED
    with pytest.raises(InvalidStateTransition):
        alert.acknowledge()
    alert.resolve()
    with pytest.raises(InvalidStateTransition):
        alert.resolve()


def test_plus_15_percent_scales_volume_and_collection():
    baseline = Baseline(100, Decimal("0.68"), Money.of(1000))
    p = simulate(baseline, Assumptions(volume_growth=Decimal("0.15")))
    assert p.projected_count == 115
    assert p.projected_collection == Money.of(78200)
    assert p.delta_pct == Decimal("0.15")


def test_baseline_from_kpis_matches_gross_collection():
    kpis = compute_kpis([tx("1", A, "1000"), tx("2", A, "3000"), tx("3", D, "500")])
    assert Baseline.from_kpis(kpis).gross_collection == Money.of(4000)


def test_simulator_bounds():
    with pytest.raises(DomainError):
        simulate(Baseline(10, Decimal("0.9"), Money.of(10)),
                 Assumptions(Decimal("0"), acceptance_change=Decimal("0.2")))


def test_observed_baseline_makes_growth_exact():
    """+15 % is exactly +15 % of the ledger total, whatever the rounding of the average ticket."""
    from tests.factories import A, D, tx

    rows = [tx("a", A, "1000.01"), tx("b", A, "1000.02"), tx("c", A, "1000.02"), tx("d", D, "50.00")]
    base = Baseline.from_kpis(compute_kpis(rows))
    assert base.gross_collection == Money.of("3000.05")
    p = simulate(base, Assumptions(volume_growth=Decimal("0.15")))
    assert p.projected_collection == Money.of("3450.06")  # 3000.05 x 1.15 = 3450.0575
    assert p.delta_collection == Money.of("450.01")
    better = simulate(base, Assumptions(volume_growth=Decimal(0), acceptance_change=Decimal("0.25")))
    assert better.projected_collection == Money.of("4000.07")  # share 0.75 -> 1.0: x 4/3
