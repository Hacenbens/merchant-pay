from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.container import (
    get_activity_profile,
    get_collections_summary,
    get_dashboard_uc,
    get_decline_radar,
    get_scope,
    get_today,
)
from app.contexts.analytics.application.get_collections import GetCollectionsSummary
from app.contexts.analytics.application.get_dashboard import GetDashboard
from app.contexts.analytics.application.get_insights import GetActivityProfile, GetDeclineRadar
from app.contexts.analytics.domain.activity import (
    MIN_ACCEPTED_FOR_PATTERN,
    MIN_DAYS_FOR_PATTERN,
    Bucket,
)
from app.contexts.analytics.domain.decline_signal import (
    CREDIBLE_MASS,
    DECISION_PROBABILITY,
    MIN_ATTEMPTS,
    PRIOR,
    DeclineEstimate,
    DeclineSignal,
    Verdict,
)
from app.contexts.analytics.domain.kpis import Granularity, KpiSnapshot
from app.contexts.analytics.domain.period_comparison import ChangeKind, PeriodChange
from app.shared.api.schemas import MoneyOut, PeriodOut, RateOut, period_from_query
from app.shared.domain.enums import Channel, TransactionStatus
from app.shared.domain.merchant_scope import MerchantScope

router = APIRouter(prefix="/analytics", tags=["analytics"])


class StatusTotalOut(BaseModel):
    status: TransactionStatus
    count: int
    amount: MoneyOut


class KpiOut(BaseModel):
    total_count: int
    accepted_count: int
    gross_collected: MoneyOut
    average_ticket: MoneyOut | None
    acceptance_rate: RateOut
    decline_rate: RateOut
    refunded_amount: MoneyOut
    by_status: list[StatusTotalOut]

    @classmethod
    def of(cls, k: KpiSnapshot) -> "KpiOut":
        return cls(
            total_count=k.total_count, accepted_count=k.accepted_count,
            gross_collected=MoneyOut.of(k.gross_collected),
            average_ticket=MoneyOut.of(k.average_ticket) if k.average_ticket else None,
            acceptance_rate=RateOut.of(k.acceptance_rate), decline_rate=RateOut.of(k.decline_rate),
            refunded_amount=MoneyOut.of(k.refunded_amount),
            by_status=[StatusTotalOut(status=s.status, count=s.count, amount=MoneyOut.of(s.amount))
                       for s in k.by_status.values()],
        )


class ChangeOut(BaseModel):
    current: int
    previous: int
    delta: int
    pct: float | None
    kind: ChangeKind

    @classmethod
    def of(cls, c: PeriodChange) -> "ChangeOut":
        return cls(current=c.current, previous=c.previous, delta=c.delta,
                   pct=float(c.pct) if c.pct is not None else None, kind=c.kind)


class SeriesPointOut(BaseModel):
    bucket_start: date
    accepted_amount: MoneyOut
    accepted_count: int


class ChannelOut(BaseModel):
    channel: Channel
    count: int
    count_share: RateOut
    accepted_amount: MoneyOut
    amount_share: RateOut


class DashboardOut(BaseModel):
    period: PeriodOut
    previous_period: PeriodOut
    granularity: Granularity
    kpis: KpiOut
    previous_kpis: KpiOut
    collected_change: ChangeOut  # values in centimes
    accepted_count_change: ChangeOut  # values in counts
    series: list[SeriesPointOut]
    channels: list[ChannelOut]


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    date_from: date | None = None,
    date_to: date | None = None,
    granularity: Granularity = Granularity.DAY,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: GetDashboard = Depends(get_dashboard_uc),
) -> DashboardOut:
    d = uc.execute(scope, period_from_query(date_from, date_to, today), granularity)
    return DashboardOut(
        period=PeriodOut.of(d.period),
        previous_period=PeriodOut.of(d.previous_period),
        granularity=granularity,
        kpis=KpiOut.of(d.kpis),
        previous_kpis=KpiOut.of(d.previous_kpis),
        collected_change=ChangeOut.of(d.collected_change),
        accepted_count_change=ChangeOut.of(d.accepted_count_change),
        series=[SeriesPointOut(bucket_start=p.bucket_start,
                               accepted_amount=MoneyOut.of(p.accepted_amount),
                               accepted_count=p.accepted_count) for p in d.series],
        channels=[ChannelOut(channel=c.channel, count=c.count, count_share=RateOut.of(c.count_share),
                             accepted_amount=MoneyOut.of(c.accepted_amount),
                             amount_share=RateOut.of(c.amount_share)) for c in d.channels],
    )


# ---- collections (module 03): status-separated totals, period A vs period B ------------
collections_router = APIRouter(prefix="/collections", tags=["collections"])


class StatusSummaryOut(BaseModel):
    status: TransactionStatus
    count_a: int
    count_b: int
    amount_a: MoneyOut
    amount_b: MoneyOut
    count_change: ChangeOut
    amount_change: ChangeOut


class CollectionsSummaryOut(BaseModel):
    period_a: PeriodOut
    period_b: PeriodOut
    total_count_a: int
    total_count_b: int
    total_count_change: ChangeOut
    collected_a: MoneyOut
    collected_b: MoneyOut
    collected_change: ChangeOut
    acceptance_rate_a: RateOut
    acceptance_rate_b: RateOut
    by_status: list[StatusSummaryOut]


@collections_router.get("/summary", response_model=CollectionsSummaryOut)
def collections_summary(
    a_from: date | None = None,
    a_to: date | None = None,
    b_from: date | None = None,
    b_to: date | None = None,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: GetCollectionsSummary = Depends(get_collections_summary),
) -> CollectionsSummaryOut:
    period_a = period_from_query(a_from, a_to, today)
    # B is optional: default to the like-for-like period immediately before A.
    period_b = period_from_query(b_from, b_to, today) if (b_from or b_to) else period_a.previous()
    s = uc.execute(scope, period_a, period_b)
    a, b = s.totals_a, s.totals_b
    return CollectionsSummaryOut(
        period_a=PeriodOut.of(s.period_a),
        period_b=PeriodOut.of(s.period_b),
        total_count_a=a.total_count,
        total_count_b=b.total_count,
        total_count_change=ChangeOut.of(s.total_count_change),
        collected_a=MoneyOut.of(a.gross_collected),
        collected_b=MoneyOut.of(b.gross_collected),
        collected_change=ChangeOut.of(s.collected_change),
        acceptance_rate_a=RateOut.of(a.acceptance_rate),
        acceptance_rate_b=RateOut.of(b.acceptance_rate),
        by_status=[
            StatusSummaryOut(status=c.status, count_a=c.a.count, count_b=c.b.count,
                             amount_a=MoneyOut.of(c.a.amount), amount_b=MoneyOut.of(c.b.amount),
                             count_change=ChangeOut.of(c.count_change),
                             amount_change=ChangeOut.of(c.amount_change))
            for c in s.by_status
        ],
    )


# ---- activity periods (module 04): high- and low-activity periods -------------------------
class BucketOut(BaseModel):
    accepted_count: int
    accepted_amount: MoneyOut

    @classmethod
    def of(cls, b: Bucket) -> "BucketOut":
        return cls(accepted_count=b.accepted_count, accepted_amount=MoneyOut.of(b.accepted_amount))


class WeekdayActivityOut(BaseModel):
    weekday: int  # 0 = Monday
    occurrences: int
    total: BucketOut
    average_amount_per_day: MoneyOut | None


class HourActivityOut(BaseModel):
    hour: int
    total: BucketOut


class DayActivityOut(BaseModel):
    day: date
    total: BucketOut


class ActivityOut(BaseModel):
    period: PeriodOut
    accepted_count: int
    pattern_sufficient: bool
    min_accepted_for_pattern: int
    min_days_for_pattern: int
    weekdays: list[WeekdayActivityOut]
    hours: list[HourActivityOut]
    busiest_days: list[DayActivityOut]
    quietest_days: list[DayActivityOut]
    peak_weekday: int | None
    quiet_weekday: int | None
    peak_hour: int | None


@router.get("/activity", response_model=ActivityOut)
def activity(
    date_from: date | None = None,
    date_to: date | None = None,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: GetActivityProfile = Depends(get_activity_profile),
) -> ActivityOut:
    p = uc.execute(scope, period_from_query(date_from, date_to, today))
    day = lambda d: DayActivityOut(day=d.day, total=BucketOut.of(d.total))  # noqa: E731
    return ActivityOut(
        period=PeriodOut.of(p.period),
        accepted_count=p.accepted_count,
        pattern_sufficient=p.pattern_sufficient,
        min_accepted_for_pattern=MIN_ACCEPTED_FOR_PATTERN,
        min_days_for_pattern=MIN_DAYS_FOR_PATTERN,
        weekdays=[WeekdayActivityOut(
            weekday=w.weekday, occurrences=w.occurrences, total=BucketOut.of(w.total),
            average_amount_per_day=(MoneyOut.of(w.average_amount_per_day)
                                    if w.average_amount_per_day else None))
            for w in p.weekdays],
        hours=[HourActivityOut(hour=h.hour, total=BucketOut.of(h.total)) for h in p.hours],
        busiest_days=[day(d) for d in p.busiest_days],
        quietest_days=[day(d) for d in p.quietest_days],
        peak_weekday=p.peak_weekday,
        quiet_weekday=p.quiet_weekday,
        peak_hour=p.peak_hour,
    )


# ---- insights: Collection Opportunity Radar (Beta-Binomial decline signal) ----------------
insights_router = APIRouter(prefix="/insights", tags=["insights"])


class DeclineEstimateOut(BaseModel):
    observed: RateOut  # declined / (accepted + declined)
    declined_amount: MoneyOut
    posterior_alpha: float
    posterior_beta: float
    mean: float
    lower: float
    upper: float
    sufficient: bool

    @classmethod
    def of(cls, e: DeclineEstimate) -> "DeclineEstimateOut":
        return cls(observed=RateOut.of(e.observed), declined_amount=MoneyOut.of(e.declined_amount),
                   posterior_alpha=e.posterior_alpha, posterior_beta=e.posterior_beta,
                   mean=e.mean, lower=e.lower, upper=e.upper, sufficient=e.sufficient)


class DeclineSignalOut(BaseModel):
    channel: Channel | None  # null = all channels
    current: DeclineEstimateOut
    previous: DeclineEstimateOut
    probability_higher: float
    verdict: Verdict

    @classmethod
    def of(cls, s: DeclineSignal) -> "DeclineSignalOut":
        return cls(channel=s.channel, current=DeclineEstimateOut.of(s.current),
                   previous=DeclineEstimateOut.of(s.previous),
                   probability_higher=s.probability_higher, verdict=s.verdict)


class MethodOut(BaseModel):
    name: str = "beta_binomial"
    prior_alpha: float
    prior_beta: float
    credible_mass: float
    decision_probability: float
    min_attempts: int


class DeclineRadarOut(BaseModel):
    period: PeriodOut
    previous_period: PeriodOut
    method: MethodOut
    overall: DeclineSignalOut
    channels: list[DeclineSignalOut]


@insights_router.get("/decline", response_model=DeclineRadarOut)
def decline(
    date_from: date | None = None,
    date_to: date | None = None,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: GetDeclineRadar = Depends(get_decline_radar),
) -> DeclineRadarOut:
    r = uc.execute(scope, period_from_query(date_from, date_to, today))
    return DeclineRadarOut(
        period=PeriodOut.of(r.period),
        previous_period=PeriodOut.of(r.previous_period),
        method=MethodOut(prior_alpha=PRIOR.alpha, prior_beta=PRIOR.beta, credible_mass=CREDIBLE_MASS,
                         decision_probability=DECISION_PROBABILITY, min_attempts=MIN_ATTEMPTS),
        overall=DeclineSignalOut.of(r.overall),
        channels=[DeclineSignalOut.of(s) for s in r.channels],
    )
