"""Read-only insight use cases: decline radar (Beta-Binomial), activity periods, Merchant Pulse."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.contexts.analytics.application.get_dashboard import TransactionReader
from app.contexts.analytics.domain.activity import ActivityProfile, activity_profile
from app.contexts.analytics.domain.decline_signal import DeclineSignal, decline_radar
from app.contexts.analytics.domain.pulse import PulseItem, build_pulse
from app.contexts.identity.domain.model import Merchant
from app.shared.domain.date_range import DateRange
from app.shared.domain.merchant_scope import MerchantScope


@dataclass(frozen=True, slots=True)
class DeclineRadar:
    period: DateRange
    previous_period: DateRange
    overall: DeclineSignal
    channels: list[DeclineSignal]


class GetDeclineRadar:
    def __init__(self, reader: TransactionReader) -> None:
        self._reader = reader

    def execute(self, scope: MerchantScope, period: DateRange) -> DeclineRadar:
        previous = period.previous()
        overall, channels = decline_radar(self._reader.list_in_period(scope, period),
                                          self._reader.list_in_period(scope, previous))
        return DeclineRadar(period, previous, overall, channels)


class GetActivityProfile:
    def __init__(self, reader: TransactionReader) -> None:
        self._reader = reader

    def execute(self, scope: MerchantScope, period: DateRange) -> ActivityProfile:
        return activity_profile(self._reader.list_in_period(scope, period), period)


class MerchantProfileReader(Protocol):
    """Port for the monthly goal. Implemented by identity's SqlMerchantRepository."""

    def get(self, merchant_id: str) -> Merchant | None: ...


@dataclass(frozen=True, slots=True)
class Pulse:
    period: DateRange
    previous_period: DateRange
    as_of: date
    items: list[PulseItem]


class GetPulse:
    def __init__(self, reader: TransactionReader, merchants: MerchantProfileReader) -> None:
        self._reader, self._merchants = reader, merchants

    def execute(self, scope: MerchantScope, period: DateRange, today: date) -> Pulse:
        previous = period.previous()
        month = DateRange.inclusive(today.replace(day=1), today)
        merchant = self._merchants.get(scope.merchant_id)
        items = build_pulse(
            self._reader.list_in_period(scope, period),
            self._reader.list_in_period(scope, previous),
            period,
            self._reader.list_in_period(scope, month),
            merchant.monthly_goal if merchant else None,
            today,
        )
        return Pulse(period, previous, today, items)
