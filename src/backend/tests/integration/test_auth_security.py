"""Login throttling (429 + Retry-After) and login audit events."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEventRow

LOGIN = "/api/v1/auth/login"


def test_sixth_failure_is_throttled_even_with_the_right_password(client):
    for _ in range(5):
        assert client.post(LOGIN, json={"email": "one@test.dz", "password": "bad"}).status_code == 401
    r = client.post(LOGIN, json={"email": "one@test.dz", "password": "pw-one"})
    assert r.status_code == 429
    assert 0 < int(r.headers["Retry-After"]) <= 900
    assert r.json()["code"] == "TooManyAttempts"
    # another account from the same IP is still allowed (IP limit is higher)
    assert client.post(LOGIN, json={"email": "two@test.dz", "password": "pw-two"}).status_code == 204


def test_successful_login_resets_counter_and_is_audited(client, seeded):
    for _ in range(4):
        client.post(LOGIN, json={"email": "one@test.dz", "password": "bad"})
    assert client.post(LOGIN, json={"email": "one@test.dz", "password": "pw-one"}).status_code == 204
    for _ in range(4):  # counter was reset: 4 more failures still do not throttle
        assert client.post(LOGIN, json={"email": "one@test.dz", "password": "bad"}).status_code == 401
    with Session(seeded) as s:
        events = s.scalars(select(AuditEventRow).where(AuditEventRow.action == "auth.login")).all()
        assert len(events) == 1 and events[0].actor_id is not None
