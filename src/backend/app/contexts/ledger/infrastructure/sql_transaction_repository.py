"""SQLAlchemy adapter. Implements ledger ports AND analytics.TransactionReader (structural typing)."""

from collections.abc import Iterable, Mapping, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.contexts.ledger.application.ports import PageRequest, TransactionFilter, TransactionPage
from app.contexts.ledger.domain.import_batch import ImportBatch
from app.contexts.ledger.domain.transaction import Transaction
from app.db.models import ImportBatchRow, MerchantRow, TransactionRow
from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import Channel, DataOrigin, TransactionStatus
from app.shared.domain.merchant_scope import MerchantScope
from app.shared.domain.money import Money


def _to_domain(row: TransactionRow) -> Transaction:
    return Transaction(
        transaction_id=row.transaction_id,
        merchant_id=row.merchant_id,
        occurred_at=row.occurred_at,
        amount=Money(row.amount_centimes),
        channel=Channel(row.channel),
        status=TransactionStatus(row.status),
        category=row.category,
        data_origin=DataOrigin(row.data_origin),
        source_batch_id=row.source_batch_id,
        customer_token=row.customer_token,
    )


class SqlTransactionRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    # ---- scoped reads -------------------------------------------------
    @staticmethod
    def _scoped(scope: MerchantScope) -> Select:
        return select(TransactionRow).where(TransactionRow.merchant_id == scope.merchant_id)

    @staticmethod
    def _in_period(stmt: Select, period: DateRange) -> Select:
        return stmt.where(TransactionRow.occurred_at >= period.start_datetime(),
                          TransactionRow.occurred_at < period.end_datetime())

    def search(self, scope: MerchantScope, flt: TransactionFilter,
               page: PageRequest) -> TransactionPage:
        stmt = self._scoped(scope)
        if flt.period:
            stmt = self._in_period(stmt, flt.period)
        if flt.statuses:
            stmt = stmt.where(TransactionRow.status.in_([s.value for s in flt.statuses]))
        if flt.channels:
            stmt = stmt.where(TransactionRow.channel.in_([c.value for c in flt.channels]))
        if flt.query:
            stmt = stmt.where(TransactionRow.transaction_id.ilike(f"%{flt.query.strip()}%"))
        total = self._s.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self._s.scalars(
            stmt.order_by(TransactionRow.occurred_at.desc(), TransactionRow.transaction_id)
            .limit(page.size).offset((page.number - 1) * page.size)
        ).all()
        return TransactionPage([_to_domain(r) for r in rows], total, page.number, page.size)

    def get(self, scope: MerchantScope, transaction_id: str) -> Transaction | None:
        row = self._s.scalar(self._scoped(scope).where(TransactionRow.transaction_id == transaction_id))
        return _to_domain(row) if row else None

    def list_in_period(self, scope: MerchantScope, period: DateRange) -> list[Transaction]:
        rows = self._s.scalars(
            self._in_period(self._scoped(scope), period).order_by(TransactionRow.occurred_at)
        ).all()
        return [_to_domain(r) for r in rows]

    # ---- writes (import / seed; not merchant-facing) --------------------
    def existing_ids(self, ids: Iterable[str]) -> set[str]:
        ids = list(ids)
        found: set[str] = set()
        for i in range(0, len(ids), 500):
            chunk = ids[i : i + 500]
            found.update(self._s.scalars(
                select(TransactionRow.transaction_id).where(TransactionRow.transaction_id.in_(chunk))
            ))
        return found

    def save_batch(self, batch: ImportBatch, transactions: Sequence[Transaction]) -> None:
        self._s.add(ImportBatchRow(batch_id=batch.batch_id, source_name=batch.source_name,
                                   data_origin=batch.data_origin.value,
                                   imported_at=batch.imported_at, row_count=batch.row_count))
        self._s.flush()
        self._s.add_all(TransactionRow(
            transaction_id=t.transaction_id, merchant_id=t.merchant_id, occurred_at=t.occurred_at,
            amount_centimes=t.amount.centimes, channel=t.channel.value, status=t.status.value,
            category=t.category, data_origin=t.data_origin.value, source_batch_id=batch.batch_id,
            customer_token=t.customer_token,
        ) for t in transactions)
        self._s.flush()


class SqlMerchantRegistry:
    """Creates placeholder merchant records for merchant IDs first seen in an import."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def ensure_exists(self, categories_by_merchant: Mapping[str, str]) -> None:
        existing = set(self._s.scalars(
            select(MerchantRow.merchant_id).where(
                MerchantRow.merchant_id.in_(list(categories_by_merchant)))
        ))
        for mid, category in categories_by_merchant.items():
            if mid not in existing:
                self._s.add(MerchantRow(merchant_id=mid, display_name=f"Marchand {mid}",
                                        category=category))
        self._s.flush()
