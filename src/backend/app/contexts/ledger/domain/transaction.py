"""Transaction entity: immutable record of one electronic payment event (source of truth)."""

from dataclasses import dataclass
from datetime import datetime

from app.shared.domain.enums import Channel, DataOrigin, TransactionStatus
from app.shared.domain.money import Money


@dataclass(frozen=True, slots=True)
class Transaction:
    transaction_id: str
    merchant_id: str
    occurred_at: datetime  # merchant-local time
    amount: Money
    channel: Channel
    status: TransactionStatus
    category: str
    data_origin: DataOrigin = DataOrigin.CHALLENGE_SOURCE
    source_batch_id: str | None = None
    # Optional pseudonymous, merchant-scoped customer reference. NOT in the official 7-field schema:
    # only enriched synthetic fixtures (or a consented future integration) carry it.
    customer_token: str | None = None
