"""Loyalty programme maths and ledger rules, checked against hand calculations."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.contexts.ledger.domain.transaction import Transaction
from app.contexts.loyalty.application.use_cases import build_baseline
from app.contexts.loyalty.domain.ledger import EntryKind, LedgerEntry, plan_accrual, summarise
from app.contexts.loyalty.domain.program import ProgramRules, ProgramVersion
from app.contexts.loyalty.domain.simulator import Scenario, simulate
from app.shared.domain.enums import Channel, TransactionStatus
from app.shared.domain.errors import DomainError
from app.shared.domain.money import Money

TODAY = date(2026, 11, 20)
A, R = TransactionStatus.ACCEPTED, TransactionStatus.REFUNDED


def tx(tid, amount, token="cus_alpha00001", days_ago=10, status=A):
    when = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time()).replace(hour=11)
    return Transaction(tid, "M1", when, Money.of(amount), Channel.POS, status, "Retail", customer_token=token)


RULES = ProgramRules(points_per_100_dzd=1, point_value=Money.of("1.00"))  # 1 % back


def test_rules_validation_and_points():
    assert RULES.reward_rate == Decimal("0.01")
    assert RULES.points_for(Money.of("1999.99")) == 19  # floor per 100 DZD
    with_min = ProgramRules(2, Money.of("0.50"), min_eligible_spend=Money.of("500.00"))
    assert with_min.points_for(Money.of("499.99")) == 0 and with_min.points_for(Money.of("500")) == 10
    for bad in (dict(points_per_100_dzd=0), dict(point_value=Money(0)), dict(expiry_days=3),
                dict(cap_points_per_customer=0), dict(campaign_budget=Money(0))):
        with pytest.raises(DomainError):
            ProgramRules(**{"points_per_100_dzd": 1, "point_value": Money.of("1"), **bad})


def _baseline(rules=RULES):
    return build_baseline(rules, [tx("T1", "1000.00"), tx("T2", "1000.00"),
                                  tx("X", "5000.00", token=None),  # untokenised: excluded
                                  tx("D", "9000.00", status=TransactionStatus.DECLINED)])


def test_scenario_equations_by_hand():
    b = _baseline()
    assert (b.tokenised_sales.centimes, b.tokenised_transactions, b.customers) == (200_000, 2, 1)
    r = simulate(RULES, b, [Scenario("base", Decimal("0.10"), Decimal("0.5"))], Decimal("0.30"), Money(0))
    s = r.results[0]
    assert s.incremental_sales == Money.of("200.00")  # 10 % of 2,000
    assert s.points_issued == 22  # floor(20 x 1.1)
    assert s.reward_liability == Money.of("22.00") and s.reward_cost == Money.of("11.00")
    assert s.reward_cost_on_existing_sales == Money.of("10.00")  # 50 % of the 20 points you'd pay anyway
    assert s.gross_contribution == Money.of("60.00") and s.net_contribution == Money.of("49.00")
    be = r.break_even[0]  # 600u >= 0.5 x floor(20(1+u)) -> u >= 1/60 = 0.0167
    assert be.uplift == Decimal("0.017") and be.incremental_sales == Money.of("34.00")
    assert be.incremental_transactions == 1


def test_no_margin_means_no_contribution_and_no_break_even():
    r = simulate(RULES, _baseline(), [Scenario("low", Decimal("0.05"), Decimal("0.3"))], None, Money(0))
    assert r.results[0].gross_contribution is None and r.results[0].net_contribution is None
    assert r.break_even[0].reason == "margin_required" and r.break_even[0].uplift is None


def test_unreachable_break_even_caps_and_budget():
    r = simulate(RULES, _baseline(), [Scenario("high", Decimal("0.2"), Decimal("1"))], Decimal("0.005"),
                 Money(0))
    assert r.break_even[0].reason == "not_reachable"  # each extra DZD costs more in rewards than margin
    capped = ProgramRules(1, Money.of("1.00"), cap_points_per_customer=15, campaign_budget=Money.of("10.00"))
    c = simulate(capped, _baseline(capped), [Scenario("base", Decimal("0.5"), Decimal("1"))], None,
                 Money.of("5.00")).results[0]
    assert c.points_issued == 15  # the cap binds whatever the uplift
    assert c.total_cost == Money.of("20.00") and c.budget_exceeded_by == Money.of("10.00")


def test_simulation_input_validation():
    with pytest.raises(DomainError):
        Scenario("base", Decimal("-0.1"), Decimal("0.5"))
    with pytest.raises(DomainError):
        simulate(RULES, _baseline(), [Scenario("base", Decimal(0), Decimal(0))], Decimal("1"), Money(0))


# ---- ledger ---------------------------------------------------------------------------------
def _program(**kw):
    return ProgramVersion(1, ProgramRules(1, Money.of("1.00"), **kw), TODAY - timedelta(days=60))


def test_accrual_is_idempotent_and_respects_window_cap_and_tokens():
    txs = [tx("T1", "1000.00", days_ago=50), tx("T2", "2500.00", days_ago=40),
           tx("OLD", "9999.00", days_ago=90),  # before effective_from
           tx("ANON", "5000.00", token=None), tx("REF", "1000.00", status=R, days_ago=5)]
    p = _program(cap_points_per_customer=30)
    first = plan_accrual(p, txs, [], TODAY)
    assert [(e.kind, e.points, e.source_transaction_id) for e in first] == [
        (EntryKind.EARN, 10, "T1"), (EntryKind.EARN, 20, "T2")]  # 25 cut to 20 by the 30-point cap
    assert first[0].idempotency_key == "earn:v1:T1"
    assert plan_accrual(p, txs, first, TODAY) == []  # replay adds nothing
    s = summarise(p, first)
    assert (s.earned, s.outstanding, s.customers_with_balance) == (30, 30, 1)
    assert s.liability == Money.of("30.00")


def test_expiry_and_refunds_never_reverse_without_a_link():
    p = _program(expiry_days=45)
    entries = plan_accrual(p, [tx("T1", "1000.00", days_ago=50), tx("T2", "1000.00", days_ago=10),
                               tx("R1", "1000.00", status=R, days_ago=2)], [], TODAY)
    kinds = [(e.kind, e.points, e.source_transaction_id) for e in entries]
    assert (EntryKind.EXPIRE, -10, "T1") in kinds and (EntryKind.EXPIRE, -10, "T2") not in kinds
    assert not any(e.kind is EntryKind.REVERSE for e in entries)
    s = summarise(p, entries)
    assert (s.earned, s.expired, s.outstanding) == (20, 10, 10)
    assert plan_accrual(p, [tx("T1", "1000.00", days_ago=50)], entries, TODAY) == []


def test_negative_balance_is_an_integrity_error_and_budget_flag():
    p = _program(campaign_budget=Money.of("5.00"))
    bad = [LedgerEntry("cus_alpha00001", EntryKind.EXPIRE, -5, TODAY, "x", 1)]
    with pytest.raises(ValueError):
        summarise(p, bad)
    ok = plan_accrual(p, [tx("T1", "1000.00")], [], TODAY)
    assert summarise(p, ok).liability_over_budget == Money.of("5.00")
