"""Insights and activity endpoints: scoped, reconciled with the ledger, explicit about method."""

API = "/api/v1"
PERIOD = {"date_from": "2026-11-01", "date_to": "2026-11-20"}


def test_endpoints_require_auth(client):
    assert client.get(f"{API}/insights/decline").status_code == 401
    assert client.get(f"{API}/analytics/activity").status_code == 401


def test_decline_radar_is_scoped_and_discloses_method(login):
    r = login().get(f"{API}/insights/decline", params=PERIOD).json()
    assert r["method"] == {"name": "beta_binomial", "prior_alpha": 1.0, "prior_beta": 19.0,
                           "credible_mass": 0.9, "decision_probability": 0.95, "min_attempts": 20}
    o = r["overall"]
    # M1 fixture: T1, T2 accepted, T3 declined (700.00); cancelled/refunded excluded
    assert o["current"]["observed"] == {"numerator": 1, "denominator": 3, "value": 1 / 3}
    assert o["current"]["declined_amount"]["amount"] == "700.00"
    assert o["verdict"] == "insufficient_data"
    ecommerce = next(c for c in r["channels"] if c["channel"] == "ecommerce")
    assert ecommerce["current"]["observed"]["denominator"] == 2
    assert r["previous_period"] == {"date_from": "2026-10-12", "date_to": "2026-10-31"}


def test_activity_reconciles_with_accepted_ledger_and_isolates_tenants(login):
    c = login()
    a = c.get(f"{API}/analytics/activity", params=PERIOD).json()
    ledger = c.get(f"{API}/transactions", params={**PERIOD, "status": "accepted"}).json()
    assert a["accepted_count"] == ledger["total"] == 2
    assert sum(w["total"]["accepted_amount"]["centimes"] for w in a["weekdays"]) == sum(
        t["amount"]["centimes"] for t in ledger["items"]) == 350050  # M2's 99,999 is absent
    assert a["pattern_sufficient"] is False and a["peak_weekday"] is None
    assert len(a["hours"]) == 24 and len(a["weekdays"]) == 7


def test_pulse_reconciles_with_collections_summary(login):
    c = login()
    pulse = c.get(f"{API}/insights/pulse", params=PERIOD).json()
    summary = c.get(f"{API}/collections/summary",
                    params={"a_from": PERIOD["date_from"], "a_to": PERIOD["date_to"]}).json()
    first = pulse["items"][0]
    assert first["code"] == "collection_down"  # 3,500.50 vs T6's 5,000.00 on 25 Oct
    assert first["facts"]["current"] == {"kind": "money", "value": summary["collected_a"]["amount"]}
    assert first["facts"]["previous"]["value"] == summary["collected_b"]["amount"] == "5000.00"
    assert pulse["items"][-1]["code"] == "goal_not_set"
    assert pulse["as_of"] == "2026-11-20"
    assert all("99999" not in str(i["facts"]) for i in pulse["items"])  # M2 never leaks in
