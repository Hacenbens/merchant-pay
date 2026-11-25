from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contexts.identity.domain.model import Merchant, MerchantAccess, Role, User, UserStatus
from app.db.models import AuditEventRow, MerchantRow, UserMerchantAccessRow, UserRow
from app.shared.domain.errors import NotFound
from app.shared.domain.money import Money


def _user(row: UserRow) -> User:
    return User(row.id, row.email, row.password_hash, UserStatus(row.status))


class SqlUserRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get_by_email(self, email: str) -> User | None:
        row = self._s.scalar(select(UserRow).where(UserRow.email == email))
        return _user(row) if row else None

    def get(self, user_id: int) -> User | None:
        row = self._s.get(UserRow, user_id)
        return _user(row) if row else None


class SqlAccessRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def for_user(self, user_id: int) -> list[MerchantAccess]:
        rows = self._s.scalars(
            select(UserMerchantAccessRow).where(UserMerchantAccessRow.user_id == user_id)
            .order_by(UserMerchantAccessRow.merchant_id)
        ).all()
        return [MerchantAccess(r.merchant_id, Role(r.role)) for r in rows]


class SqlMerchantRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, merchant_id: str) -> Merchant | None:
        row = self._s.get(MerchantRow, merchant_id)
        if row is None:
            return None
        goal = Money(row.monthly_goal_centimes) if row.monthly_goal_centimes is not None else None
        days = tuple(d for d in row.operating_days.split(",") if d)
        return Merchant(row.merchant_id, row.display_name, row.category, row.timezone, days, goal)

    def save(self, merchant: Merchant) -> None:
        """Update in the request's unit of work; get_db() commits at the end of the request."""
        row = self._s.get(MerchantRow, merchant.merchant_id)
        if row is None:
            raise NotFound("Merchant not found")
        row.display_name = merchant.display_name
        row.category = merchant.category
        row.operating_days = ",".join(merchant.operating_days)
        row.monthly_goal_centimes = merchant.monthly_goal.centimes if merchant.monthly_goal else None
        self._s.flush()


class SqlAuditLog:
    def __init__(self, session: Session) -> None:
        self._s = session

    def record(self, actor_id: int, action: str, entity_ref: str) -> None:
        self._s.add(AuditEventRow(actor_id=actor_id, action=action, entity_ref=entity_ref[:255]))
