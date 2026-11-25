"""Commercial growth simulator (blueprint §10). Deterministic what-if, not a forecast."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.contexts.analytics.domain.kpis import KpiSnapshot
from app.shared.domain.errors import DomainError
from app.shared.domain.money import Money


@dataclass(frozen=True, slots=True)
class Baseline:
    transaction_count: int
    acceptance_share: Decimal  # accepted / all initiated transactions in the baseline period
    average_ticket: Money
    # Exact observed accepted total. When present, projections scale it directly, so +15 % is exactly
    # +15 % of the ledger (a rounded average ticket x count drifts by centimes on large volumes).
    observed_gross: Money | None = None

    @classmethod
    def from_kpis(cls, kpis: KpiSnapshot) -> "Baseline":
        if kpis.total_count == 0 or kpis.average_ticket is None:
            raise DomainError("Baseline period has no accepted activity")
        share = Decimal(kpis.accepted_count) / Decimal(kpis.total_count)
        return cls(kpis.total_count, share, kpis.average_ticket, kpis.gross_collected)

    @property
    def gross_collection(self) -> Money:
        if self.observed_gross is not None:
            return self.observed_gross
        return self.average_ticket.scale(Decimal(self.transaction_count) * self.acceptance_share)


@dataclass(frozen=True, slots=True)
class Assumptions:
    volume_growth: Decimal  # 0.15 == +15 %
    acceptance_change: Decimal = Decimal(0)  # absolute points, e.g. 0.02
    ticket_change: Decimal = Decimal(0)  # relative, e.g. 0.05 == +5 %

    def __post_init__(self) -> None:
        if not Decimal("-1") <= self.volume_growth <= Decimal("10"):
            raise DomainError("volume_growth must be between -100% and +1000%")
        if not Decimal("-1") < self.ticket_change <= Decimal("10"):
            raise DomainError("ticket_change must be between -100% and +1000%")


@dataclass(frozen=True, slots=True)
class Projection:
    projected_count: int  # rounded for display
    projected_accepted_count: Decimal  # exact
    projected_acceptance_share: Decimal
    projected_average_ticket: Money
    projected_collection: Money
    delta_collection: Money
    delta_pct: Decimal | None


def simulate(baseline: Baseline, a: Assumptions) -> Projection:
    count = Decimal(baseline.transaction_count) * (1 + a.volume_growth)
    share = baseline.acceptance_share + a.acceptance_change
    if not Decimal(0) <= share <= Decimal(1):
        raise DomainError("Resulting acceptance rate must stay within 0-100%")
    ticket = baseline.average_ticket.scale(1 + a.ticket_change)
    accepted = count * share
    if baseline.observed_gross is not None:
        factor = (1 + a.volume_growth) * (share / baseline.acceptance_share) * (1 + a.ticket_change)
        collection = baseline.observed_gross.scale(factor)
    else:
        collection = ticket.scale(accepted)
    base = baseline.gross_collection
    delta = collection - base
    pct = Decimal(delta.centimes) / Decimal(base.centimes) if base.centimes else None
    return Projection(
        projected_count=int(count.quantize(Decimal(1), rounding=ROUND_HALF_UP)),
        projected_accepted_count=accepted,
        projected_acceptance_share=share,
        projected_average_ticket=ticket,
        projected_collection=collection,
        delta_collection=delta,
        delta_pct=pct,
    )


# TODO(stretch): solve_for_goal(baseline, goal) -> the volume growth needed to cover a goal.
