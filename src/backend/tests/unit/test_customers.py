"""Customer intelligence rules on hand-built histories (no DB)."""

from datetime import date, datetime, timedelta

import pytest

from app.contexts.customers.domain.profiles import (
    Availability,
    Segment,
    SegmentRules,
    build_book,
    new_vs_returning,
    repeat_rate,
)
from app.contexts.customers.domain.reengagement import (
    Decision,
    MerchantDecision,
    Suggestion,
    reengagement_list,
    validate_decision,
)
from app.contexts.customers.domain.winback import (
    BaselineSource,
    ReturnStatus,
    WinbackRules,
    pooled_baseline,
    purchase_intervals,
    return_status,
)
from app.contexts.ledger.domain.row_parsing import parse_customer_token
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import Channel, TransactionStatus
from app.shared.domain.errors import DomainError
from app.shared.domain.money import Money

AS_OF = date(2026, 11, 20)
A, D, R = TransactionStatus.ACCEPTED, TransactionStatus.DECLINED, TransactionStatus.REFUNDED


def days_ago(*ns):
    return [AS_OF - timedelta(days=n) for n in ns]


def ctx(token, n_days_ago, amount="1000.00", status=A, tid=None):
    when = datetime.combine(AS_OF - timedelta(days=n_days_ago), datetime.min.time()).replace(hour=10)
    return Transaction(tid or f"{token}-{n_days_ago}-{status.value}", "M1", when, Money.of(amount),
                       Channel.POS, status, "Retail", customer_token=token)


# ---- tokens ---------------------------------------------------------------------------------
def test_token_guard_refuses_card_like_values():
    assert parse_customer_token("cus_ab12cd34ef56gh78") == "cus_ab12cd34ef56gh78"
    assert parse_customer_token("") is None and parse_customer_token(None) is None
    for bad in ("4111111111111111", "cus_4111111111111111", "short", "has space x", "a" * 65):
        with pytest.raises(ValueError):
            parse_customer_token(bad)


# ---- win-back -------------------------------------------------------------------------------
def test_intervals_use_distinct_days():
    assert purchase_intervals(days_ago(30, 20, 20, 10)) == [10, 10]


def test_personal_baseline_and_bands():
    rhythm = [70, 63, 56, 49, 42, 35, 28]  # every 7 days, last purchase 28 days ago
    e = return_status(days_ago(*rhythm), AS_OF, None)
    assert e.baseline.source is BaselineSource.PERSONAL and e.baseline.median_days == 7
    assert e.baseline.spread_days == 0
    assert e.thresholds.at_risk_days == 17.5 and e.thresholds.lapsed_days == 60
    assert e.status is ReturnStatus.AT_RISK and e.ratio == 4.0 and e.rule_version == "winback-v1"
    assert return_status(days_ago(*[r - 25 for r in rhythm]), AS_OF, None).status is ReturnStatus.NORMAL
    assert return_status(days_ago(*[r - 17 for r in rhythm]), AS_OF, None).status is ReturnStatus.WATCH
    assert return_status(days_ago(*[r + 40 for r in rhythm]), AS_OF, None).status is ReturnStatus.LAPSED


def test_fallbacks_pooled_insufficient_and_single_purchase():
    pooled = pooled_baseline([days_ago(*range(100, 0, -10))] * 3, WinbackRules())
    assert pooled.source is BaselineSource.POOLED and pooled.intervals == 27 and pooled.median_days == 10
    two = return_status(days_ago(50, 40), AS_OF, pooled)  # one own interval -> pooled baseline
    assert two.baseline is pooled and two.status is ReturnStatus.AT_RISK
    assert return_status(days_ago(50, 40), AS_OF, None).status is ReturnStatus.INSUFFICIENT_HISTORY
    assert pooled_baseline([days_ago(3, 2, 1)], WinbackRules()) is None  # 2 intervals < 20
    assert return_status(days_ago(5), AS_OF, pooled).status is ReturnStatus.NOT_REPEAT


# ---- profiles and segments ------------------------------------------------------------------
def _crowd(n=20):
    """n steady weekly customers so the book is 'available' and the pooled baseline exists."""
    return [ctx(f"cus_steady{i:02d}xx", d) for i in range(n) for d in range(84, 0, -7)]


def test_segments_precedence_and_separate_value_flag():
    txs = _crowd() + [
        ctx("cus_newcomerxx", 3),
        ctx("cus_oncexxxxxx", 100),
        *[ctx("cus_driftedxxx", d, amount="9000.00") for d in (91, 84, 77, 70, 63, 56, 49)],
        ctx("cus_refundedxx", 10), ctx("cus_refundedxx", 5, amount="500.00", status=R),
        ctx("cus_refundedxx", 4, amount="700.00", status=D),
    ]
    book = build_book(txs, AS_OF)
    seg = {p.token: p for p in book.profiles}
    assert book.availability is Availability.AVAILABLE
    assert seg["cus_newcomerxx"].segment is Segment.NEW
    assert seg["cus_oncexxxxxx"].segment is Segment.ONE_TIME
    assert seg["cus_driftedxxx"].segment is Segment.AT_RISK  # gap 49 days vs a 7-day rhythm
    assert seg["cus_steady00xx"].segment is Segment.LOYAL
    # refunded/declined rows are not purchases and are not netted: value = the one accepted sale
    r = seg["cus_refundedxx"]
    assert (r.frequency, r.monetary.centimes, r.segment) == (1, 100_000, Segment.NEW)
    assert seg["cus_driftedxxx"].high_value is True  # spends most, yet at risk: value != loyalty
    assert seg["cus_steady00xx"].high_value is False
    assert seg["cus_steady00xx"].alias == "••••00XX"


def test_availability_states_and_coverage():
    untokenised = Transaction("T1", "M1", datetime(2026, 11, 10, 9), Money.of("50.00"), Channel.POS, A, "R")
    assert build_book([untokenised], AS_OF).availability is Availability.NO_CUSTOMER_IDENTIFIER
    few = build_book([untokenised, ctx("cus_onlyonexx", 2)], AS_OF)
    assert few.availability is Availability.INSUFFICIENT_HISTORY and few.high_value_threshold is None
    assert all(p.high_value is None for p in few.profiles)
    assert (few.coverage.share.numerator, few.coverage.share.denominator) == (1, 2)


def test_window_bounds_frequency_and_eligibility():
    rules = SegmentRules(window_days=30)
    book = build_book([ctx("cus_oldtimerxx", 200), ctx("cus_oldtimerxx", 10), ctx("cus_goneawayxx", 90)],
                      AS_OF, rules)
    assert [p.token for p in book.profiles] == ["cus_oldtimerxx"]  # gone-away: nothing in window
    p = book.profiles[0]
    assert (p.frequency, p.lifetime_purchases, p.recency_days) == (1, 2, 10)
    assert repeat_rate(book).denominator == 1 and repeat_rate(book).numerator == 0


def test_new_vs_returning_uses_all_history_for_first_seen():
    txs = [ctx("cus_returnerxx", 40), ctx("cus_returnerxx", 5), ctx("cus_firsttime", 3)]
    split = new_vs_returning(txs, DateRange.inclusive(AS_OF - timedelta(days=13), AS_OF))
    assert (split.new.customers, split.returning.customers) == (1, 1)
    assert split.returning.accepted_value.centimes == 100_000  # only the in-period purchase


# ---- re-engagement --------------------------------------------------------------------------
def test_priority_suggestions_and_merchant_decisions():
    txs = _crowd() + [*[ctx("cus_bigdriftxx", d, amount="9000.00") for d in (70, 63, 56, 49, 42)],
                      *[ctx("cus_smalldrift", d, amount="10.00") for d in (70, 63, 56, 49, 42)],
                      *[ctx("cus_watchingxx", d) for d in (40, 33, 26, 19, 12)]]
    book = build_book(txs, AS_OF)
    entries = reengagement_list(book, {}, AS_OF)
    order = [(e.profile.token, e.suggestion) for e in entries]
    assert order == [("cus_bigdriftxx", Suggestion.SERVICE_FOLLOW_UP),
                     ("cus_smalldrift", Suggestion.GENERAL_OFFER),
                     ("cus_watchingxx", Suggestion.NO_ACTION_YET)]
    assert entries[2].recheck_on == AS_OF - timedelta(days=12) + timedelta(days=18)  # ceil(17.5)

    now = datetime(2026, 11, 20, 12)
    decisions = {"cus_bigdriftxx": MerchantDecision("cus_bigdriftxx", Decision.DISMISS, None, now),
                 "cus_smalldrift": MerchantDecision("cus_smalldrift", Decision.SNOOZE, AS_OF, now)}
    visible = [e.profile.token for e in reengagement_list(book, decisions, AS_OF)]
    assert visible == ["cus_smalldrift", "cus_watchingxx"]  # snooze ended today -> visible again
    assert len(reengagement_list(book, decisions, AS_OF, include_hidden=True)) == 3


def test_decision_validation():
    validate_decision(Decision.SNOOZE, AS_OF + timedelta(days=7), AS_OF)
    bad = ((Decision.SNOOZE, None), (Decision.SNOOZE, AS_OF), (Decision.SNOOZE, AS_OF + timedelta(91)),
           (Decision.DISMISS, AS_OF + timedelta(days=1)))
    for d, until in bad:
        with pytest.raises(DomainError):
            validate_decision(d, until, AS_OF)
