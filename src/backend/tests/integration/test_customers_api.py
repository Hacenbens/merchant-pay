"""Customer endpoints over HTTP + SQL: availability, evidence, decisions, and tenant isolation."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contexts.ledger.application.import_transactions import ImportTransactions
from app.contexts.ledger.infrastructure.sql_transaction_repository import (
    SqlMerchantRegistry,
    SqlTransactionRepository,
)
from app.db.models import AuditEventRow, CustomerActionRow
from app.shared.domain.enums import DataOrigin

API = "/api/v1/customers"
TODAY = datetime(2026, 11, 20, 10)
SHARED = "cus_sharedtoken01"  # same string at both merchants: must never be linked


def _rows(merchant, token, days_ago, amount="1000.00", status="Accepted"):
    return [{"transaction_id": f"{merchant}-{token}-{d}", "merchant_id": merchant,
             "occurred_at": TODAY - timedelta(days=d), "amount": amount, "channel": "TPE / POS",
             "status": status, "category": "Retail", "customer_token": token} for d in days_ago]


@pytest.fixture
def loyalty(seeded):
    rows = []
    for i in range(22):  # steady weekly customers at M1
        rows += _rows("M1", f"cus_weekly{i:02d}xx", range(84, 0, -7))
    rows += _rows("M1", "cus_driftingxxx", (70, 63, 56, 49, 42), amount="9000.00")
    rows += _rows("M1", SHARED, (30, 20, 10))
    rows += _rows("M2", SHARED, (60, 50, 40, 30), amount="77777.00")  # other tenant
    rows += _rows("M2", "cus_onlyatbxxx", (5,))
    with Session(seeded) as s, s.begin():
        report = ImportTransactions(SqlTransactionRepository(s), SqlMerchantRegistry(s)).execute(
            enumerate(rows, start=2), source_name="loyalty-fixture", data_origin=DataOrigin.SYNTHETIC_DEMO)
        assert report.ok, report.errors
    return seeded


def test_unavailable_without_tokens_and_auth_required(client, login):
    assert client.get(f"{API}/overview").status_code == 401
    o = login().get(f"{API}/overview").json()  # base fixture has no customer_token at all
    assert o["book"]["availability"] == "no_customer_identifier"
    assert o["book"]["eligible_customers"] == 0 and o["repeat_rate"]["value"] is None


def test_overview_discloses_window_coverage_and_rules(loyalty, login):
    o = login().get(f"{API}/overview", params={"date_from": "2026-11-07", "date_to": "2026-11-20"}).json()
    b = o["book"]
    assert b["availability"] == "available" and b["eligible_customers"] == 24
    assert b["window"] == {"date_from": "2026-05-25", "date_to": "2026-11-20"}
    # base fixture's untokenised M1 sales count in coverage, M2 rows never do
    assert b["coverage"]["share"]["denominator"] == b["coverage"]["tokenised_in_window"] + 3
    assert b["rules"]["segments_version"] == "segments-v1" and b["rules"]["winback_version"] == "winback-v1"
    seg = {r["segment"]: r for r in o["segments"]}
    assert seg["at_risk"]["customers"] == 1 and seg["at_risk"]["accepted_value"]["amount"] == "45000.00"
    assert sum(r["customers"] for r in o["segments"]) == 24
    assert "77777" not in str(o)


def test_detail_is_merchant_scoped_even_for_an_identical_token(loyalty, login):
    a = login().get(f"{API}/{SHARED}").json()
    assert a["customer"]["lifetime_purchases"] == 3  # only M1's three purchases
    assert a["customer"]["alias"] == "••••EN01"
    assert {s["status"]: s["count"] for s in a["statuses"]}["accepted"] == 3
    c = login()
    assert c.get(f"{API}/cus_onlyatbxxx").status_code == 404  # M2's customer
    assert c.get(f"{API}/cus_doesnotexist").status_code == 404
    assert c.get(f"{API}/bad token!").status_code in (404, 422)


def test_reengagement_shows_evidence_and_decisions_are_scoped_and_audited(loyalty, login, seeded):
    c = login()
    r = c.get(f"{API}/reengagement").json()
    first = r["entries"][0]
    assert first["customer"]["token"] == "cus_driftingxxx"
    ev = first["customer"]["evidence"]
    assert ev["status"] == "at_risk" and ev["gap_days"] == 42 and ev["baseline"]["median_days"] == 7
    assert ev["baseline"]["source"] == "personal" and ev["rule_version"] == "winback-v1"
    assert first["suggestion"] in ("service_follow_up", "general_offer")

    ok = c.post(f"{API}/cus_driftingxxx/decisions", json={"decision": "snooze", "snooze_until": "2026-11-27"})
    assert ok.status_code == 201, ok.text
    after = c.get(f"{API}/reengagement").json()
    assert "cus_driftingxxx" not in [e["customer"]["token"] for e in after["entries"]]
    assert after["hidden_count"] == 1
    assert c.post(f"{API}/cus_driftingxxx/decisions", json={"decision": "snooze"}).status_code == 422
    assert c.post(f"{API}/cus_onlyatbxxx/decisions", json={"decision": "dismiss"}).status_code == 404

    with Session(seeded) as s:
        actions = s.scalars(select(CustomerActionRow)).all()
        assert [(a.merchant_id, a.action) for a in actions] == [("M1", "snooze")]
        audit = s.scalars(select(AuditEventRow).where(AuditEventRow.action == "customer.decision")).all()
        assert len(audit) == 1 and "cus_" not in audit[0].entity_ref  # token masked in the audit log


def test_other_merchant_sees_only_its_own_customers(loyalty, login):
    b = login("two@test.dz", "pw-two").get(f"{API}/overview").json()
    assert b["book"]["eligible_customers"] == 2 and b["book"]["availability"] == "insufficient_history"
    page = login("two@test.dz", "pw-two").get(API).json()
    assert {p["token"] for p in page["items"]} == {SHARED, "cus_onlyatbxxx"}
    assert next(p for p in page["items"] if p["token"] == SHARED)["monetary"]["amount"] == "311108.00"


def test_list_filters_and_window_validation(loyalty, login):
    c = login()
    at_risk = c.get(API, params={"status": "at_risk"}).json()
    assert [p["token"] for p in at_risk["items"]] == ["cus_driftingxxx"] and at_risk["total"] == 1
    assert c.get(API, params={"window_days": 10}).status_code == 422
    assert c.get(API, params={"size": 500}).status_code == 422
