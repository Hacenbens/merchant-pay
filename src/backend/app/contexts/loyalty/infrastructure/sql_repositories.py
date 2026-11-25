from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.contexts.loyalty.application.use_cases import SimulationRun, rules_from_dict, rules_to_dict
from app.contexts.loyalty.domain.ledger import EntryKind, LedgerEntry
from app.contexts.loyalty.domain.program import ProgramRules, ProgramVersion
from app.db.models import LoyaltyLedgerEntryRow, LoyaltyProgramRow, LoyaltyScenarioRunRow
from app.shared.domain.errors import InvalidStateTransition
from app.shared.domain.merchant_scope import MerchantScope


def _program(row: LoyaltyProgramRow) -> ProgramVersion:
    return ProgramVersion(row.version, rules_from_dict(row.rules), row.effective_from, row.created_at,
                          row.created_by)


class SqlProgramRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def current(self, scope: MerchantScope) -> ProgramVersion | None:
        row = self._s.scalar(select(LoyaltyProgramRow)
                             .where(LoyaltyProgramRow.merchant_id == scope.merchant_id)
                             .order_by(LoyaltyProgramRow.version.desc()).limit(1))
        return _program(row) if row else None

    def add(self, scope: MerchantScope, rules: ProgramRules, effective_from: date) -> ProgramVersion:
        latest = self._s.scalar(select(func.max(LoyaltyProgramRow.version))
                                .where(LoyaltyProgramRow.merchant_id == scope.merchant_id)) or 0
        row = LoyaltyProgramRow(merchant_id=scope.merchant_id, version=latest + 1, rules=rules_to_dict(rules),
                                effective_from=effective_from, created_by=scope.user_id)
        try:
            with self._s.begin_nested():
                self._s.add(row)
                self._s.flush()
        except IntegrityError as exc:  # two saves raced for the same version number
            raise InvalidStateTransition("The programme was changed concurrently; reload and retry") from exc
        return _program(row)


class SqlLedgerRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def entries(self, scope: MerchantScope, version: int) -> list[LedgerEntry]:
        rows = self._s.scalars(select(LoyaltyLedgerEntryRow).where(
            LoyaltyLedgerEntryRow.merchant_id == scope.merchant_id,
            LoyaltyLedgerEntryRow.program_version == version)).all()
        return [LedgerEntry(r.customer_token, EntryKind(r.kind), r.points, r.occurred_on, r.idempotency_key,
                            r.program_version, r.source_transaction_id) for r in rows]

    def add_all(self, scope: MerchantScope, entries: list[LedgerEntry]) -> None:
        if not entries:
            return
        try:
            with self._s.begin_nested():
                self._s.add_all(LoyaltyLedgerEntryRow(
                    merchant_id=scope.merchant_id, program_version=e.program_version,
                    customer_token=e.customer_token, kind=e.kind.value, points=e.points,
                    occurred_on=e.occurred_on, source_transaction_id=e.source_transaction_id,
                    idempotency_key=e.idempotency_key) for e in entries)
                self._s.flush()
        except IntegrityError as exc:  # a concurrent run already wrote some of these keys
            raise InvalidStateTransition("Accrual already recorded by a concurrent run; retry") from exc


class SqlSimulationRunRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, scope: MerchantScope, inputs: dict, results: dict) -> SimulationRun:
        row = LoyaltyScenarioRunRow(merchant_id=scope.merchant_id, created_by=scope.user_id,
                                    inputs=inputs, results=results)
        self._s.add(row)
        self._s.flush()
        return SimulationRun(row.id, row.created_at, row.inputs, row.results)

    def recent(self, scope: MerchantScope, limit: int) -> list[SimulationRun]:
        rows = self._s.scalars(select(LoyaltyScenarioRunRow)
                               .where(LoyaltyScenarioRunRow.merchant_id == scope.merchant_id)
                               .order_by(LoyaltyScenarioRunRow.id.desc()).limit(limit)).all()
        return [SimulationRun(r.id, r.created_at, r.inputs, r.results) for r in rows]
