"""PATCH /merchant/me: validated partial update, owner-only, tenant-scoped, audited."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.container import get_password_hasher
from app.db.models import AuditEventRow, MerchantRow
from app.seed.accounts import ensure_user

API = "/api/v1"


def test_partial_update_persists_and_is_audited(login, seeded):
    c = login()
    r = c.patch(f"{API}/merchant/me", json={"display_name": "  Épicerie Un  ",
                                             "operating_days": ["sat", "sun", "mon"],
                                             "monthly_goal_centimes": 150_000_000})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["display_name"] == "Épicerie Un"
    assert body["operating_days"] == ["sun", "mon", "sat"]  # canonical order
    assert body["monthly_goal"]["amount"] == "1500000.00"
    assert body["category"] == "Retail"  # not sent -> unchanged

    me = c.get(f"{API}/merchant/me").json()["merchant"]
    assert me["display_name"] == "Épicerie Un" and me["monthly_goal"]["centimes"] == 150_000_000

    with Session(seeded) as s:
        other = s.get(MerchantRow, "M2")
        assert other.display_name == "Merchant Two"  # other tenant untouched
        events = s.scalars(select(AuditEventRow)).all()
        assert [e.action for e in events] == ["merchant.profile_updated"]
        assert events[0].entity_ref == "merchant:M1 fields:display_name,monthly_goal,operating_days"


def test_null_goal_clears_it_and_empty_body_is_a_no_op(login):
    c = login()
    c.patch(f"{API}/merchant/me", json={"monthly_goal_centimes": 5000})
    assert c.patch(f"{API}/merchant/me", json={"monthly_goal_centimes": None}).json()["monthly_goal"] is None
    assert c.patch(f"{API}/merchant/me", json={}).status_code == 200


def test_invalid_input_is_rejected(login):
    c = login()
    for bad in ({"display_name": ""}, {"display_name": "   "}, {"operating_days": []},
                {"operating_days": ["mon-fri"]}, {"monthly_goal_centimes": -1},
                {"merchant_id": "M2"}, {"category": "x" * 101}):
        r = c.patch(f"{API}/merchant/me", json=bad)
        assert r.status_code == 422, (bad, r.status_code, r.text)
    assert c.get(f"{API}/merchant/me").json()["merchant"]["display_name"] == "Merchant One"


def test_staff_cannot_edit_and_anonymous_is_rejected(client, seeded, login):
    assert client.patch(f"{API}/merchant/me", json={"display_name": "x"}).status_code == 401
    with Session(seeded) as s, s.begin():
        ensure_user(s, get_password_hasher(), "staff@test.dz", "pw-staff", "M1", role="staff")
    c = login("staff@test.dz", "pw-staff")
    assert c.patch(f"{API}/merchant/me", json={"display_name": "x"}).status_code == 403
