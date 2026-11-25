"""Composition root: the ONLY module that knows concrete implementations.

Routers depend on these providers via FastAPI Depends(). Tests swap any of them with
app.dependency_overrides[provider] = lambda: Fake(...).
"""

from collections.abc import Iterator
from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.contexts.alerts.application.evaluate_alerts import EvaluateAlerts
from app.contexts.alerts.application.manage_alerts import (
    AcknowledgeAlert,
    ListAlerts,
    ResolveAlert,
)
from app.contexts.alerts.infrastructure.sql_alert_repository import SqlAlertRepository
from app.contexts.analytics.application.get_collections import GetCollectionsSummary
from app.contexts.analytics.application.get_dashboard import GetDashboard
from app.contexts.analytics.application.get_insights import GetActivityProfile, GetDeclineRadar
from app.contexts.identity.application.use_cases import (
    Authenticate,
    GetMe,
    ResolveScope,
    UpdateMerchantProfile,
)
from app.contexts.identity.infrastructure.security import Argon2PasswordHasher, JwtTokenService
from app.contexts.identity.infrastructure.sql_repositories import (
    SqlAccessRepository,
    SqlAuditLog,
    SqlMerchantRepository,
    SqlUserRepository,
)
from app.contexts.ledger.application.queries import GetTransaction, SearchTransactions
from app.contexts.ledger.infrastructure.sql_transaction_repository import SqlTransactionRepository
from app.contexts.simulation.application.run_simulation import RunGrowthSimulation
from app.contexts.simulation.infrastructure.sql_scenario_repository import SqlScenarioRunRepository
from app.db.session import make_engine, make_session_factory
from app.shared.domain.merchant_scope import MerchantScope

SESSION_COOKIE = "mp_session"


# ---- infrastructure --------------------------------------------------------
@lru_cache
def _session_factory() -> sessionmaker:
    return make_session_factory(make_engine(get_settings().database_url))


def get_db() -> Iterator[Session]:
    """One session (= one unit of work) per request; commit on success."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_today(settings: Settings = Depends(get_settings)) -> date:
    """Injectable clock: DEMO_TODAY (or a test override) freezes 'today' for reproducibility."""
    if settings.demo_today is not None:
        return settings.demo_today
    return datetime.now(ZoneInfo(settings.timezone)).date()


@lru_cache
def get_password_hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


def get_token_service(settings: Settings = Depends(get_settings)) -> JwtTokenService:
    return JwtTokenService(settings.jwt_secret, settings.jwt_ttl_minutes)


# ---- identity ----------------------------------------------------------------
def get_authenticate(db: Session = Depends(get_db), hasher=Depends(get_password_hasher),
                     tokens=Depends(get_token_service)) -> Authenticate:
    return Authenticate(SqlUserRepository(db), hasher, tokens)


def get_current_user_id(request: Request, tokens=Depends(get_token_service)) -> int:
    token = request.cookies.get(SESSION_COOKIE)
    user_id = tokens.decode(token) if token else None
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user_id


def get_scope(
    user_id: int = Depends(get_current_user_id),
    x_merchant_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> MerchantScope:
    """Tenant isolation entry point. Use Depends(get_scope) on EVERY merchant endpoint."""
    return ResolveScope(SqlAccessRepository(db)).execute(user_id, x_merchant_id)


def get_me_uc(db: Session = Depends(get_db)) -> GetMe:
    return GetMe(SqlUserRepository(db), SqlAccessRepository(db), SqlMerchantRepository(db))


def get_merchant_repository(db: Session = Depends(get_db)) -> SqlMerchantRepository:
    return SqlMerchantRepository(db)


def get_audit_log(db: Session = Depends(get_db)) -> SqlAuditLog:
    return SqlAuditLog(db)


def get_update_merchant_profile(
    merchants: SqlMerchantRepository = Depends(get_merchant_repository),
    audit: SqlAuditLog = Depends(get_audit_log),
) -> UpdateMerchantProfile:
    return UpdateMerchantProfile(merchants, audit)


# ---- ledger -------------------------------------------------------------------
def get_transaction_repository(db: Session = Depends(get_db)) -> SqlTransactionRepository:
    return SqlTransactionRepository(db)


def get_search_transactions(repo=Depends(get_transaction_repository)) -> SearchTransactions:
    return SearchTransactions(repo)


def get_get_transaction(repo=Depends(get_transaction_repository)) -> GetTransaction:
    return GetTransaction(repo)


# ---- analytics ----------------------------------------------------------------
def get_dashboard_uc(repo=Depends(get_transaction_repository)) -> GetDashboard:
    # analytics.TransactionReader port <- ledger SQL adapter
    return GetDashboard(repo)


def get_collections_summary(
    repo=Depends(get_transaction_repository),
) -> GetCollectionsSummary:
    return GetCollectionsSummary(repo)


def get_decline_radar(repo=Depends(get_transaction_repository)) -> GetDeclineRadar:
    return GetDeclineRadar(repo)


def get_activity_profile(repo=Depends(get_transaction_repository)) -> GetActivityProfile:
    return GetActivityProfile(repo)


# ---- alerts -------------------------------------------------------------------
def get_alert_repository(db: Session = Depends(get_db)) -> SqlAlertRepository:
    return SqlAlertRepository(db)


def get_evaluate_alerts(
    repo: SqlAlertRepository = Depends(get_alert_repository),
    merchants: SqlMerchantRepository = Depends(get_merchant_repository),
    transactions: SqlTransactionRepository = Depends(get_transaction_repository),
) -> EvaluateAlerts:
    # alerts.TransactionReader + alerts.MerchantProfileReader ports <- ledger/identity adapters
    return EvaluateAlerts(transactions, repo, merchants)


def get_list_alerts(repo: SqlAlertRepository = Depends(get_alert_repository)) -> ListAlerts:
    return ListAlerts(repo)


def get_acknowledge_alert(
    repo: SqlAlertRepository = Depends(get_alert_repository),
) -> AcknowledgeAlert:
    return AcknowledgeAlert(repo)


def get_resolve_alert(repo: SqlAlertRepository = Depends(get_alert_repository)) -> ResolveAlert:
    return ResolveAlert(repo)


# ---- simulation ---------------------------------------------------------------
def get_scenario_repository(db: Session = Depends(get_db)) -> SqlScenarioRunRepository:
    return SqlScenarioRunRepository(db)


def get_run_growth_simulation(
    transactions: SqlTransactionRepository = Depends(get_transaction_repository),
    scenarios: SqlScenarioRunRepository = Depends(get_scenario_repository),
    merchants: SqlMerchantRepository = Depends(get_merchant_repository),
) -> RunGrowthSimulation:
    return RunGrowthSimulation(transactions, scenarios, merchants)
