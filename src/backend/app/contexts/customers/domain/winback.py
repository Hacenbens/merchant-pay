"""Quiet-churn / win-back radar: compare a customer's current silence with their own return rhythm.

Rule version winback-v1. A HEURISTIC RISK BAND, not a churn probability: no labelled churn
outcomes exist, so nothing here is calibrated. Every status carries the evidence that produced it.

Baseline (in days between distinct accepted-purchase days):
- personal, when the customer has >= min_personal_intervals intervals;
- otherwise pooled over all repeat customers of this merchant, when >= min_pooled_intervals exist;
- otherwise no baseline -> INSUFFICIENT_HISTORY.
Spread is the scaled median absolute deviation (1.4826 x MAD), robust to one odd gap.

Thresholds on the current gap g (days since the last accepted purchase):
  watch   : g >= max(watch_ratio   x median, median + k_watch x spread, watch_min_days)
  at risk : g >= max(at_risk_ratio x median, median + k_risk  x spread, at_risk_min_days)
  lapsed  : g >= max(lapsed_ratio  x median, lapsed_min_days)
Single-purchase customers are NOT_REPEAT: they never established a rhythm to drift from.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

MAD_SCALE = 1.4826


@dataclass(frozen=True, slots=True)
class WinbackRules:
    version: str = "winback-v1"
    min_personal_intervals: int = 2
    min_pooled_intervals: int = 20
    watch_ratio: float = 1.5
    at_risk_ratio: float = 2.5
    lapsed_ratio: float = 4.0
    k_watch: float = 2.0
    k_risk: float = 4.0
    watch_min_days: int = 7
    at_risk_min_days: int = 14
    lapsed_min_days: int = 60


class ReturnStatus(StrEnum):
    NORMAL = "normal"
    WATCH = "watch"
    AT_RISK = "at_risk"
    LAPSED = "lapsed"
    INSUFFICIENT_HISTORY = "insufficient_history"
    NOT_REPEAT = "not_repeat"


class BaselineSource(StrEnum):
    PERSONAL = "personal"
    POOLED = "pooled"


@dataclass(frozen=True, slots=True)
class Baseline:
    source: BaselineSource
    median_days: float
    spread_days: float
    intervals: int


@dataclass(frozen=True, slots=True)
class Thresholds:
    watch_days: float
    at_risk_days: float
    lapsed_days: float


@dataclass(frozen=True, slots=True)
class ReturnEvidence:
    status: ReturnStatus
    last_purchase: date
    gap_days: int
    purchase_days: int  # distinct days with an accepted purchase (all history up to as_of)
    baseline: Baseline | None
    thresholds: Thresholds | None
    ratio: float | None  # gap / baseline median
    rule_version: str


def purchase_intervals(days: Sequence[date]) -> list[int]:
    """Gaps between consecutive DISTINCT purchase days (two purchases the same day are one visit)."""
    distinct = sorted(set(days))
    return [(b - a).days for a, b in zip(distinct, distinct[1:], strict=False)]


def robust_baseline(intervals: Sequence[int], source: BaselineSource) -> Baseline:
    med = statistics.median(intervals)
    mad = statistics.median(abs(x - med) for x in intervals)
    return Baseline(source, float(med), MAD_SCALE * float(mad), len(intervals))


def pooled_baseline(all_days: Iterable[Sequence[date]], rules: WinbackRules) -> Baseline | None:
    pool = [i for days in all_days for i in purchase_intervals(days)]
    if len(pool) < rules.min_pooled_intervals:
        return None
    return robust_baseline(pool, BaselineSource.POOLED)


def thresholds_for(b: Baseline, rules: WinbackRules) -> Thresholds:
    return Thresholds(
        watch_days=max(rules.watch_ratio * b.median_days, b.median_days + rules.k_watch * b.spread_days,
                       rules.watch_min_days),
        at_risk_days=max(rules.at_risk_ratio * b.median_days, b.median_days + rules.k_risk * b.spread_days,
                         rules.at_risk_min_days),
        lapsed_days=max(rules.lapsed_ratio * b.median_days, rules.lapsed_min_days),
    )


def return_status(days: Sequence[date], as_of: date, pooled: Baseline | None,
                  rules: WinbackRules = WinbackRules()) -> ReturnEvidence:
    distinct = sorted({d for d in days if d <= as_of})
    if not distinct:
        raise ValueError("a customer needs at least one accepted purchase")
    last = distinct[-1]
    gap = (as_of - last).days
    base = dict(last_purchase=last, gap_days=gap, purchase_days=len(distinct), rule_version=rules.version)
    if len(distinct) < 2:
        return ReturnEvidence(ReturnStatus.NOT_REPEAT, baseline=None, thresholds=None, ratio=None, **base)

    own = purchase_intervals(distinct)
    baseline = (robust_baseline(own, BaselineSource.PERSONAL)
                if len(own) >= rules.min_personal_intervals else pooled)
    if baseline is None or baseline.median_days <= 0:
        return ReturnEvidence(ReturnStatus.INSUFFICIENT_HISTORY, baseline=baseline, thresholds=None,
                              ratio=None, **base)
    t = thresholds_for(baseline, rules)
    if gap >= t.lapsed_days:
        status = ReturnStatus.LAPSED
    elif gap >= t.at_risk_days:
        status = ReturnStatus.AT_RISK
    elif gap >= t.watch_days:
        status = ReturnStatus.WATCH
    else:
        status = ReturnStatus.NORMAL
    return ReturnEvidence(status, baseline=baseline, thresholds=t, ratio=gap / baseline.median_days, **base)
