"""Loyalty endpoints: owner-only programme, scoped simulations, idempotent pilot ledger."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.container import get_password_hasher
from app.contexts.ledger.application.import_transactions import ImportTransactions
from app.contexts.ledger.infrastructure.sql_transaction_repository import (
    SqlMerchantRegistry,
    SqlTransactionRepository,
)
from app.contexts.loyalty.domain.ledger import EntryKind, LedgerEntry
from app.contexts.loyalty.infrastructure.sql_repositories import SqlLedgerRepository
from app.db.models import AuditEventRow, LoyaltyLedgerEntryRow
from app.seed.accounts import ensure_user
from app.shared.domain.enums import DataOrigin
from app.shared.domain.errors import InvalidStateTransition
from app.shared.domain.merchant_scope import MerchantScope

API = "/api/v1/loyalty"
TODAY = datetime(2026, 11, 20, 10)
RULES = {"points_per_100_dzd": 1, "point_value_centimes": 100}
PROGRAM = {"rules": RULES, "effective_from": "2026-09-01"}
SIM = {"rules": RULES, "gross_margin": "0.30", "window_days": 90,
       "scenarios": [{"name": "low", "uplift": "0", "redemption_rate": "0.3"},
                     {"name": "base", "uplift": "0.05", "redemption_rate": "0.5"}]}


@pytest.fixture
def loyalty(seeded):
    rows = [{"transaction_id": f"{m}-{tok}-{d}", "merchant_id": m, "occurred_at": TODAY - timedelta(days=d),
             "amount": amt, "channel": "TPE / POS", "status": "Accepted", "category": "Retail",
             "customer_token": tok}
            for m, tok, amt in (("M1", "cus_loyalone01", "1000.00"), ("M2", "cus_loyaltwo01", "50000.00"))
            for d in (40, 20, 10)]
    with Session(seeded) as s, s.begin():
        assert ImportTransactions(SqlTransactionRepository(s), SqlMerchantRegistry(s)).execute(
            enumerate(rows, start=2), source_name="loyalty", data_origin=DataOrigin.SYNTHETIC_DEMO).ok
        ensure_user(s, get_password_hasher(), "staff@test.dz", "pw-staff", "M1", role="staff")
    return seeded


def test_programme_is_owner_only_versioned_and_audited(loyalty, login, seeded):
    c = login()
    assert c.get(f"{API}/program").json() == {"program": None}
    v1 = c.put(f"{API}/program", json=PROGRAM)
    assert v1.status_code == 200 and v1.json()["version"] == 1 and v1.json()["rules"]["reward_rate"] == 0.01
    v2 = c.put(f"{API}/program", json={**PROGRAM, "rules": {**RULES, "expiry_days": 90}})
    assert v2.json()["version"] == 2
    bad = {**PROGRAM, "rules": {**RULES, "points_per_100_dzd": 0}}
    assert c.put(f"{API}/program", json=bad).status_code == 422
    assert c.put(f"{API}/program", json={**PROGRAM, "effective_from": "2020-01-01"}).status_code == 422
    assert c.put(f"{API}/program", json={**PROGRAM, "merchant_id": "M2"}).status_code == 422
    staff = login("staff@test.dz", "pw-staff")
    assert staff.put(f"{API}/program", json=PROGRAM).status_code == 403
    assert staff.post(f"{API}/ledger/accrue").status_code == 403
    assert login("two@test.dz", "pw-two").get(f"{API}/program").json() == {"program": None}  # isolated
    with Session(seeded) as s:
        acts = s.scalars(select(AuditEventRow.action).where(AuditEventRow.action.like("loyalty.%"))).all()
        assert acts == ["loyalty.program_saved", "loyalty.program_saved"]


def test_simulation_uses_only_own_history_and_is_persisted(loyalty, login):
    c = login()
    r = c.post(f"{API}/simulations", json=SIM)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["baseline"]["tokenised_sales"]["amount"] == "3000.00"  # M2's 150,000 never counted
    assert body["baseline"]["customers"] == 1
    base = next(x for x in body["results"] if x["name"] == "base")
    assert base["points_issued"] == 31 and base["reward_cost"]["amount"] == "15.50"
    assert base["net_contribution"]["amount"] == "29.50"  # 0.3 x 150 - 15.50
    assert c.post(f"{API}/simulations", json={**SIM, "gross_margin": "1.5"}).status_code == 422
    assert [s["id"] for s in c.get(f"{API}/simulations").json()] == [body["run_id"]]
    assert login("two@test.dz", "pw-two").get(f"{API}/simulations").json() == []


def test_pilot_accrual_is_idempotent_and_ledger_is_scoped(loyalty, login, seeded):
    c = login()
    assert c.post(f"{API}/ledger/accrue").status_code == 404  # no programme yet
    c.put(f"{API}/program", json=PROGRAM)
    first = c.post(f"{API}/ledger/accrue").json()
    assert (first["created_earn"], first["already_recorded"]) == (3, 0)
    again = c.post(f"{API}/ledger/accrue").json()
    assert (again["created_earn"], again["created_expire"], again["already_recorded"]) == (0, 0, 3)
    led = c.get(f"{API}/ledger").json()
    assert led["summary"]["earned"] == 30 and led["summary"]["liability"]["amount"] == "30.00"
    assert {e["customer"] for e in led["entries"]} == {"••••NE01"}  # masked, never the raw token
    other = login("two@test.dz", "pw-two").get(f"{API}/ledger").json()
    assert other["program"] is None and other["entries"] == []
    with Session(seeded) as s:
        assert s.scalar(select(LoyaltyLedgerEntryRow.merchant_id).distinct()) == "M1"


def test_database_rejects_a_replayed_idempotency_key(loyalty):
    with Session(loyalty) as s, s.begin():
        repo = SqlLedgerRepository(s)
        scope = MerchantScope(1, "M1", "owner")
        entry = LedgerEntry("cus_loyalone01", EntryKind.EARN, 5, TODAY.date(), "earn:v1:X", 1, "X")
        repo.add_all(scope, [entry])
        with pytest.raises(InvalidStateTransition):
            repo.add_all(scope, [entry])


def test_ledger_and_simulator_agree_on_points(loyalty, login):
    """The pilot ledger and the zero-uplift scenario use the same earning rule over the same window."""
    c = login()
    c.put(f"{API}/program", json={**PROGRAM, "effective_from": "2026-08-23"})  # = 90-day window start
    c.post(f"{API}/ledger/accrue")
    sim = c.post(f"{API}/simulations", json=SIM).json()
    low = next(x for x in sim["results"] if x["name"] == "low")
    assert low["points_issued"] == c.get(f"{API}/ledger").json()["summary"]["earned"] == 30
