"""Collection Opportunity Radar: Beta-Binomial decline-rate estimates, overall and per channel.

Model. Each authorization attempt (Accepted or Declined; Cancelled/Refunded are not issuer
decisions) is a Bernoulli trial with unknown decline probability p. Prior p ~ Beta(1, 19), a weak
prior centred on 5% worth 20 pseudo-attempts. Posterior: Beta(1 + declined, 19 + accepted).

Verdict between two equal-length windows uses the exact posterior probability that the current
decline rate exceeds the previous one, P(p_cur > p_prev): ELEVATED at >= 95%, LOWER at <= 5%,
otherwise NO_CLEAR_CHANGE. Below MIN_ATTEMPTS in either window the verdict is INSUFFICIENT_DATA,
whatever the raw rate says.

This describes WHERE declines are concentrated. It says nothing about WHY (no decline reason in the
data), and declined value is not recoverable revenue.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.contexts.analytics.domain.beta import beta_quantile, prob_greater
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.enums import Channel, TransactionStatus
from app.shared.domain.money import Money
from app.shared.domain.rate import Rate


@dataclass(frozen=True, slots=True)
class BetaPrior:
    alpha: float = 1.0
    beta: float = 19.0

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)


PRIOR = BetaPrior()
MIN_ATTEMPTS = 20
CREDIBLE_MASS = 0.90
DECISION_PROBABILITY = 0.95


class Verdict(StrEnum):
    ELEVATED = "elevated"
    LOWER = "lower"
    NO_CLEAR_CHANGE = "no_clear_change"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class DeclineEstimate:
    observed: Rate  # declined / (accepted + declined)
    declined_amount: Money
    posterior_alpha: float
    posterior_beta: float
    mean: float
    lower: float  # 5th percentile
    upper: float  # 95th percentile
    sufficient: bool


def estimate(transactions: Iterable[Transaction], prior: BetaPrior = PRIOR) -> DeclineEstimate:
    declined = accepted = 0
    declined_amount = Money.zero()
    for t in transactions:
        if t.status is TransactionStatus.DECLINED:
            declined += 1
            declined_amount = declined_amount + t.amount
        elif t.status is TransactionStatus.ACCEPTED:
            accepted += 1
    a, b = prior.alpha + declined, prior.beta + accepted
    tail = (1 - CREDIBLE_MASS) / 2
    return DeclineEstimate(
        observed=Rate(declined, declined + accepted),
        declined_amount=declined_amount,
        posterior_alpha=a,
        posterior_beta=b,
        mean=a / (a + b),
        lower=beta_quantile(tail, a, b),
        upper=beta_quantile(1 - tail, a, b),
        sufficient=declined + accepted >= MIN_ATTEMPTS,
    )


def probability_higher(current: DeclineEstimate, previous: DeclineEstimate) -> float:
    """P(current decline rate > previous decline rate) under the two posteriors."""
    return prob_greater(current.posterior_alpha, current.posterior_beta,
                        previous.posterior_alpha, previous.posterior_beta)


def verdict(current: DeclineEstimate, previous: DeclineEstimate, p_higher: float) -> Verdict:
    if not (current.sufficient and previous.sufficient):
        return Verdict.INSUFFICIENT_DATA
    if p_higher >= DECISION_PROBABILITY:
        return Verdict.ELEVATED
    if p_higher <= 1 - DECISION_PROBABILITY:
        return Verdict.LOWER
    return Verdict.NO_CLEAR_CHANGE


@dataclass(frozen=True, slots=True)
class DeclineSignal:
    channel: Channel | None  # None = all channels
    current: DeclineEstimate
    previous: DeclineEstimate
    probability_higher: float
    verdict: Verdict


def _signal(channel: Channel | None, cur: list[Transaction], prev: list[Transaction]) -> DeclineSignal:
    c, p = estimate(cur), estimate(prev)
    p_higher = probability_higher(c, p)
    return DeclineSignal(channel, c, p, p_higher, verdict(c, p, p_higher))


def decline_radar(current: Iterable[Transaction],
                  previous: Iterable[Transaction]) -> tuple[DeclineSignal, list[DeclineSignal]]:
    """Overall signal + one per channel, channels sorted by current declined value (desc)."""
    cur, prev = list(current), list(previous)
    overall = _signal(None, cur, prev)
    channels = [_signal(ch, [t for t in cur if t.channel is ch], [t for t in prev if t.channel is ch])
                for ch in Channel]
    channels.sort(key=lambda s: (-s.current.declined_amount.centimes, s.channel))
    return overall, channels
