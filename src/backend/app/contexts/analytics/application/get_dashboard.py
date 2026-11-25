from dataclasses import dataclass
from typing import Protocol

from app.contexts.analytics.domain.kpis import (
    ChannelShare,
    Granularity,
    KpiSnapshot,
    SeriesPoint,
    channel_mix,
    collection_series,
    compute_kpis,
)
from app.contexts.analytics.domain.period_comparison import PeriodChange, compare
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.date_range import DateRange
from app.shared.domain.merchant_scope import MerchantScope


class TransactionReader(Protocol):
    """Port. Implemented by ledger's SqlTransactionRepository (wired in app/container.py)."""

    def list_in_period(self, scope: MerchantScope, period: DateRange) -> list[Transaction]: ...


@dataclass(frozen=True, slots=True)
class Dashboard:
    period: DateRange
    previous_period: DateRange
    kpis: KpiSnapshot
    previous_kpis: KpiSnapshot
    collected_change: PeriodChange
    accepted_count_change: PeriodChange
    series: list[SeriesPoint]
    channels: list[ChannelShare]


class GetDashboard:
    def __init__(self, reader: TransactionReader) -> None:
        self._reader = reader

    def execute(self, scope: MerchantScope, period: DateRange,
                granularity: Granularity = Granularity.DAY) -> Dashboard:
        prev_period = period.previous()
        current = self._reader.list_in_period(scope, period)
        previous = self._reader.list_in_period(scope, prev_period)
        kpis, prev_kpis = compute_kpis(current), compute_kpis(previous)
        return Dashboard(
            period=period,
            previous_period=prev_period,
            kpis=kpis,
            previous_kpis=prev_kpis,
            collected_change=compare(kpis.gross_collected.centimes,
                                     prev_kpis.gross_collected.centimes),
            accepted_count_change=compare(kpis.accepted_count, prev_kpis.accepted_count),
            series=collection_series(current, period, granularity),
            channels=channel_mix(current),
        )
