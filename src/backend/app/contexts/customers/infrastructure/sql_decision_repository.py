from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contexts.customers.domain.reengagement import Decision, MerchantDecision
from app.db.models import CustomerActionRow
from app.shared.domain.merchant_scope import MerchantScope


def _domain(row: CustomerActionRow) -> MerchantDecision:
    return MerchantDecision(row.customer_token, Decision(row.action), row.snooze_until, row.created_at)


class SqlDecisionRepository:
    """Append-only: a new decision never overwrites an old one; the latest one wins."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def latest(self, scope: MerchantScope) -> dict[str, MerchantDecision]:
        rows = self._s.scalars(
            select(CustomerActionRow).where(CustomerActionRow.merchant_id == scope.merchant_id)
            .order_by(CustomerActionRow.created_at, CustomerActionRow.id)
        ).all()
        out: dict[str, MerchantDecision] = {}
        for r in rows:
            if r.action == Decision.CLEAR.value:
                out.pop(r.customer_token, None)
            else:
                out[r.customer_token] = _domain(r)
        return out

    def add(self, scope: MerchantScope, token: str, decision: Decision,
            snooze_until: date | None) -> MerchantDecision:
        row = CustomerActionRow(merchant_id=scope.merchant_id, customer_token=token, action=decision.value,
                                snooze_until=snooze_until, actor_id=scope.user_id)
        self._s.add(row)
        self._s.flush()
        return _domain(row)
