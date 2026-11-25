"""Beta distribution CDF and quantile in pure Python (no SciPy dependency).

Used only for statistical estimates (credible intervals), never for money. The regularized
incomplete beta function uses the Lentz continued fraction (Numerical Recipes §6.4); the
quantile is found by bisection, which is slow-but-certain and plenty fast for a handful of calls.
"""

from __future__ import annotations

import math

_EPS = 1e-14
_TINY = 1e-300


def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > _TINY else _TINY)
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > _TINY else _TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > _TINY else _TINY
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > _TINY else _TINY)
        c = 1.0 + aa / c
        c = c if abs(c) > _TINY else _TINY
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            break
    return h


def beta_cdf(x: float, a: float, b: float) -> float:
    """P(X <= x) for X ~ Beta(a, b)."""
    if a <= 0 or b <= 0:
        raise ValueError("Beta parameters must be positive")
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                 + a * math.log(x) + b * math.log1p(-x))
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def beta_quantile(p: float, a: float, b: float) -> float:
    """Inverse CDF: the x such that P(X <= x) = p."""
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be within [0, 1]")
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if beta_cdf(mid, a, b) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def prob_greater(a1: float, b1: float, a2: float, b2: float) -> float:
    """Exact P(X1 > X2) for independent X1 ~ Beta(a1, b1), X2 ~ Beta(a2, b2).

    Closed form (Evan Miller, "Formulas for Bayesian A/B testing"); requires integer a1.
    """
    if a1 != int(a1) or a1 < 1:
        raise ValueError("prob_greater requires a positive integer a1")
    base = _log_beta(a2, b2)
    total = 0.0
    for i in range(int(a1)):
        total += math.exp(_log_beta(a2 + i, b1 + b2) - math.log(b1 + i)
                          - _log_beta(1 + i, b1) - base)
    return min(1.0, max(0.0, total))
