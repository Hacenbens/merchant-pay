"""Read-only insight use cases: decline radar (Beta-Binomial) and activity periods."""

from dataclasses import dataclass

from app.contexts.analytics.application.get_dashboard import TransactionReader
from app.contexts.analytics.domain.activity import ActivityProfile, activity_profile
from app.contexts.analytics.domain.decline_signal import DeclineSignal, decline_radar
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
