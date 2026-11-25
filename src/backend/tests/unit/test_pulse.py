"""Merchant Pulse rules: every fact is reproducible from the ledger; drivers sum exactly."""

from datetime import date
from decimal import Decimal

from app.contexts.analytics.domain.pulse import PulseCode, Tone, build_pulse
from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import Channel
from app.shared.domain.money import Money
from tests.factories import A, D, tx

PERIOD = DateRange.inclusive(date(2026, 11, 7), date(2026, 11, 20))
TODAY = date(2026, 11, 20)


def _codes(items):
    return [i.code for i in items]


def _by_code(items, code):
    return next(i for i in items if i.code is code)


def _sales(prefix, n, amount, when="2026-11-10 10:00", channel=Channel.POS):
    return [tx(f"{prefix}{i}", A, amount, when=when, channel=channel) for i in range(n)]


def test_collection_drop_with_exact_driver_decomposition():
    prev = _sales("p", 10, "1000.00", when="2026-11-01 10:00")
    cur = _sales("c", 4, "1250.00")
    items = build_pulse(cur, prev, PERIOD, [], None, TODAY)
    down = _by_code(items, PulseCode.COLLECTION_DOWN)
    assert down.tone is Tone.NEGATIVE
    assert down.facts["current"].value == "5000.00" and down.facts["previous"].value == "10000.00"
    assert down.facts["delta"].value == "-5000.00" and down.facts["change"].value == "-0.5000"
    assert down.evidence == "status=accepted&date_from=2026-11-07&date_to=2026-11-20"

    drivers = _by_code(items, PulseCode.COLLECTION_DRIVERS)
    volume = Decimal(drivers.facts["volume_effect"].value)
    ticket = Decimal(drivers.facts["ticket_effect"].value)
    assert volume == Decimal("-6000.00")  # (4 - 10) x 1000
    assert ticket == Decimal("1000.00")  # 4 x (1250 - 1000)
    assert volume + ticket == Decimal(down.facts["delta"].value)
    assert drivers.facts["driver"].value == "volume"


def test_small_change_is_stable_and_empty_periods_are_explicit():
    stable = build_pulse(_sales("c", 100, "102.00"), _sales("p", 100, "100.00"), PERIOD, [], None, TODAY)
    assert PulseCode.COLLECTION_STABLE in _codes(stable)
    assert _codes(build_pulse([], [], PERIOD, [], None, TODAY)) == [PulseCode.NO_ACTIVITY,
                                                                    PulseCode.GOAL_NOT_SET]
    new = build_pulse(_sales("c", 1, "10.00"), [], PERIOD, [], None, TODAY)
    assert _codes(new)[0] is PulseCode.COLLECTION_NEW
    assert PulseCode.COLLECTION_DRIVERS not in _codes(new)  # no baseline ticket to compare


def test_declines_note_concentration_but_keep_the_channel_sample_gate():
    cur = (_sales("c", 60, "100.00") + _sales("e", 10, "100.00", channel=Channel.ECOMMERCE)
           + [tx(f"d{i}", D, "500.00", channel=Channel.ECOMMERCE) for i in range(7)]
           + [tx(f"dp{i}", D, "500.00") for i in range(3)])
    prev = _sales("p", 145, "100.00", when="2026-11-01 10:00") + [
        tx(f"x{i}", D, "100.00", when="2026-11-01 10:00") for i in range(5)]
    item = _by_code(build_pulse(cur, prev, PERIOD, [], None, TODAY), PulseCode.DECLINES)
    f = item.facts
    assert (f["declined"].value, f["attempts"].value, f["declined_amount"].value) == ("10", "80", "5000.00")
    assert f["verdict"].value == "elevated" and item.tone is Tone.NEGATIVE
    assert f["top_channel"].value == "ecommerce" and f["top_share"].value == "0.7000"
    assert f["top_attempts"].value == "17" and f["top_verdict"].value == "insufficient_data"
    assert item.evidence.endswith("&channel=ecommerce")


def test_goal_pace_uses_month_to_date_and_linear_pace():
    goal = Money.of("30000.00")  # Nov: 30 days -> 1000/day; by the 20th, 20000 expected
    month = _sales("m", 15, "1000.00", when="2026-11-05 10:00")
    behind = _by_code(build_pulse([], [], PERIOD, month, goal, TODAY), PulseCode.GOAL_BEHIND)
    assert behind.facts["collected"].value == "15000.00"
    assert behind.facts["expected_by_now"].value == "20000.00"
    assert behind.facts["remaining"].value == "15000.00"
    assert behind.facts["days_left"].value == "10" and behind.facts["daily_needed"].value == "1500.00"
    assert behind.facts["progress"].value == "0.5000"

    on_track = build_pulse([], [], PERIOD, _sales("m", 21, "1000.00", when="2026-11-05 10:00"), goal, TODAY)
    assert PulseCode.GOAL_ON_TRACK in _codes(on_track)
    reached = build_pulse([], [], PERIOD, _sales("m", 30, "1000.00", when="2026-11-05 10:00"), goal, TODAY)
    item = _by_code(reached, PulseCode.GOAL_REACHED)
    assert item.facts["remaining"].value == "0.00" and item.facts["daily_needed"].value is None
    october = _sales("o", 99, "1000.00", when="2026-10-31 10:00")  # outside the month: ignored
    assert PulseCode.GOAL_BEHIND in _codes(build_pulse([], [], PERIOD, october, goal, TODAY))
