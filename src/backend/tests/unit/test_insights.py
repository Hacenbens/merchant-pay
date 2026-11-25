"""Beta math against closed forms; decline radar and activity periods on hand-built ledgers."""

import random
from datetime import date, datetime, timedelta

import pytest

from app.contexts.analytics.domain.activity import activity_profile
from app.contexts.analytics.domain.beta import beta_cdf, beta_quantile, prob_greater
from app.contexts.analytics.domain.decline_signal import (
    MIN_ATTEMPTS,
    Verdict,
    decline_radar,
    estimate,
)
from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import Channel
from tests.factories import A, C, D, R, tx


# ---- beta ---------------------------------------------------------------------------------
@pytest.mark.parametrize("p", [0.05, 0.3, 0.5, 0.95])
def test_beta_quantile_matches_closed_forms(p):
    assert beta_quantile(p, 1, 1) == pytest.approx(p, abs=1e-9)  # uniform
    assert beta_quantile(p, 2, 1) == pytest.approx(p ** 0.5, abs=1e-9)  # cdf x^2
    assert beta_quantile(p, 1, 2) == pytest.approx(1 - (1 - p) ** 0.5, abs=1e-9)  # cdf 1-(1-x)^2


def test_beta_cdf_bounds_and_symmetry():
    assert beta_cdf(0, 3, 4) == 0 and beta_cdf(1, 3, 4) == 1
    assert beta_cdf(0.3, 3, 7) == pytest.approx(1 - beta_cdf(0.7, 7, 3), abs=1e-12)


def test_prob_greater_is_exact():
    assert prob_greater(3, 10, 3, 10) == pytest.approx(0.5, abs=1e-12)
    rng = random.Random(7)
    n = 100_000
    mc = sum(rng.betavariate(11, 83) > rng.betavariate(7, 161) for _ in range(n)) / n
    assert prob_greater(11, 83, 7, 161) == pytest.approx(mc, abs=0.005)
    with pytest.raises(ValueError):
        prob_greater(1.5, 2, 1, 1)


# ---- decline radar ------------------------------------------------------------------------
def _ledger(prefix, accepted, declined, channel=Channel.POS, extra=()):
    rows = [tx(f"{prefix}A{i}", A, "100", channel=channel) for i in range(accepted)]
    rows += [tx(f"{prefix}D{i}", D, "250", channel=channel) for i in range(declined)]
    return rows + list(extra)


def test_estimate_uses_authorization_decisions_only():
    e = estimate(_ledger("x", 18, 2, extra=[tx("c", C, "999"), tx("r", R, "999")]))
    assert (e.observed.numerator, e.observed.denominator) == (2, 20)
    assert e.declined_amount.centimes == 2 * 25_000
    assert (e.posterior_alpha, e.posterior_beta) == (3, 37)  # Beta(1,19) prior + data
    assert e.lower < e.mean < e.upper and e.sufficient


def test_small_samples_are_insufficient_even_with_extreme_rates():
    overall, _ = decline_radar(_ledger("c", 2, MIN_ATTEMPTS - 3), _ledger("p", 100, 1))
    assert overall.verdict is Verdict.INSUFFICIENT_DATA


def test_clear_spike_is_elevated_and_stable_rate_is_not():
    spike, _ = decline_radar(_ledger("c", 60, 20), _ledger("p", 145, 5))
    assert spike.verdict is Verdict.ELEVATED and spike.probability_higher >= 0.95
    flat, _ = decline_radar(_ledger("c", 95, 5), _ledger("p", 94, 6))
    assert flat.verdict is Verdict.NO_CLEAR_CHANGE
    drop, _ = decline_radar(_ledger("c", 145, 5), _ledger("p", 60, 20))
    assert drop.verdict is Verdict.LOWER


def test_channels_are_separate_and_sorted_by_declined_value():
    cur = _ledger("e", 30, 15, Channel.ECOMMERCE) + _ledger("p", 40, 2, Channel.POS)
    prev = _ledger("E", 48, 2, Channel.ECOMMERCE) + _ledger("P", 40, 2, Channel.POS)
    overall, channels = decline_radar(cur, prev)
    assert [s.channel for s in channels[:2]] == [Channel.ECOMMERCE, Channel.POS]
    assert channels[0].verdict is Verdict.ELEVATED
    assert channels[1].verdict is Verdict.NO_CLEAR_CHANGE
    assert overall.current.observed.denominator == 87
    assert len(channels) == len(Channel)


# ---- activity periods ---------------------------------------------------------------------
def _at(day: date, hour: int) -> str:
    return datetime.combine(day, datetime.min.time()).replace(hour=hour).isoformat(sep=" ")


def test_weekday_average_is_normalised_by_occurrences():
    period = DateRange.inclusive(date(2026, 11, 2), date(2026, 11, 30))  # 5 Mondays, 4 Sundays
    rows = []
    for i in range(period.days):
        d = period.start + timedelta(days=i)
        rows.append(tx(f"T{i}", A, "1000", when=_at(d, 10 if d.weekday() else 18)))
    rows.append(tx("DECL", D, "50000", when=_at(date(2026, 11, 8), 12)))  # not collected
    p = activity_profile(rows, period)
    monday, sunday = p.weekdays[0], p.weekdays[6]
    assert (monday.occurrences, sunday.occurrences) == (5, 4)
    assert monday.total.accepted_amount.centimes == 5 * 100_000
    assert monday.average_amount_per_day == sunday.average_amount_per_day  # same daily rate
    assert p.hours[10].total.accepted_count == period.days - 5
    assert p.accepted_count == period.days == 29
    assert not p.pattern_sufficient  # 29 < MIN_ACCEPTED_FOR_PATTERN: boundary of the gate


def test_peaks_quiet_days_and_insufficient_history():
    period = DateRange.inclusive(date(2026, 11, 2), date(2026, 11, 22))  # 3 full weeks
    rows = [tx(f"F{w}{k}", A, "5000", when=_at(date(2026, 11, 6) + timedelta(weeks=w), 19))
            for w in range(3) for k in range(10)]  # busy Friday evenings
    rows += [tx(f"M{w}", A, "100", when=_at(date(2026, 11, 2) + timedelta(weeks=w), 9))
             for w in range(3)]
    p = activity_profile(rows, period)
    assert p.peak_weekday == 4 and p.peak_hour == 19
    assert p.busiest_days[0].day.weekday() == 4
    assert all(d.total.accepted_count == 0 for d in p.quietest_days)  # silent days count as low
    assert p.quiet_weekday in (1, 2, 3, 5, 6)

    thin = activity_profile(rows[:5], DateRange.inclusive(date(2026, 11, 6), date(2026, 11, 10)))
    assert not thin.pattern_sufficient and thin.peak_weekday is None and thin.peak_hour is None
