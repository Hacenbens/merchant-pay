"""Customers to re-engage: priority order, a rule-based suggestion, and the merchant's decision.

Nothing is ever sent to a customer. Suggestions are advice for the merchant, each with the reason
it was made and the reasons it may be wrong (shown in the UI).

Priority: at_risk, then watch, then lapsed; within a status, high-value first, then by historical
accepted value (desc), then token (stable order).

Suggestion rules (version reengage-v1):
  at_risk and high value -> service_follow_up   (a valuable relationship is drifting: personal check)
  at_risk                -> general_offer
  watch                  -> no_action_yet       (re-check on the day the at-risk threshold is reached)
  lapsed                 -> low_priority_offer  (long silence: an offer is cheap to try, expect little)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from app.contexts.customers.domain.profiles import CustomerBook, CustomerProfile
from app.contexts.customers.domain.winback import ReturnStatus
from app.shared.domain.errors import DomainError

RULE_VERSION = "reengage-v1"
_PRIORITY = {ReturnStatus.AT_RISK: 0, ReturnStatus.WATCH: 1, ReturnStatus.LAPSED: 2}
MAX_SNOOZE_DAYS = 90


class Suggestion(StrEnum):
    SERVICE_FOLLOW_UP = "service_follow_up"
    GENERAL_OFFER = "general_offer"
    NO_ACTION_YET = "no_action_yet"
    LOW_PRIORITY_OFFER = "low_priority_offer"


class Decision(StrEnum):
    DISMISS = "dismiss"
    SNOOZE = "snooze"
    CONTACTED = "contacted"
    CLEAR = "clear"


@dataclass(frozen=True, slots=True)
class MerchantDecision:
    token: str
    decision: Decision
    snooze_until: date | None
    decided_at: datetime


def validate_decision(decision: Decision, snooze_until: date | None, today: date) -> None:
    if decision is Decision.SNOOZE:
        if snooze_until is None or not today < snooze_until <= today + timedelta(days=MAX_SNOOZE_DAYS):
            raise DomainError(f"snooze_until must be within the next {MAX_SNOOZE_DAYS} days")
    elif snooze_until is not None:
        raise DomainError("snooze_until is only valid with the snooze decision")


@dataclass(frozen=True, slots=True)
class ReengageEntry:
    profile: CustomerProfile
    suggestion: Suggestion
    recheck_on: date | None
    decision: MerchantDecision | None
    hidden: bool  # dismissed, or snoozed until a future date


def suggest(p: CustomerProfile) -> Suggestion:
    status = p.evidence.status
    if status is ReturnStatus.AT_RISK:
        return Suggestion.SERVICE_FOLLOW_UP if p.high_value else Suggestion.GENERAL_OFFER
    if status is ReturnStatus.WATCH:
        return Suggestion.NO_ACTION_YET
    return Suggestion.LOW_PRIORITY_OFFER


def reengagement_list(book: CustomerBook, decisions: dict[str, MerchantDecision],
                      today: date, include_hidden: bool = False) -> list[ReengageEntry]:
    entries = []
    for p in book.profiles:
        if p.evidence.status not in _PRIORITY:
            continue
        d = decisions.get(p.token)
        hidden = d is not None and (d.decision is Decision.DISMISS or (
            d.decision is Decision.SNOOZE and d.snooze_until is not None and d.snooze_until > today))
        if hidden and not include_hidden:
            continue
        t = p.evidence.thresholds
        recheck = (p.last_purchase + timedelta(days=math.ceil(t.at_risk_days))
                   if p.evidence.status is ReturnStatus.WATCH and t else None)
        entries.append(ReengageEntry(p, suggest(p), recheck, d, hidden))
    entries.sort(key=lambda e: (_PRIORITY[e.profile.evidence.status], not bool(e.profile.high_value),
                                -e.profile.monetary.centimes, e.profile.token))
    return entries
