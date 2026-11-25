"""POST /simulations/lab over HTTP: scoped baseline, audit rows, validation; /growth unchanged."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ScenarioRunRow

API = "/api/v1/simulations"
PERIOD = {"baseline_from": "2026-11-01", "baseline_to": "2026-11-20"}


def test_lab_runs_named_scenarios_on_own_data_and_audits_them(login, seeded):
    c = login()
    body = {
        **PERIOD,
        "scenarios": [
            {"name": "conservative", "volume_growth": "0.05"},
            {"name": "base", "volume_growth": "0.15"},
            {
                "name": "ambitious",
                "volume_growth": "0.3",
                "ticket_change": "0.05",
                "shifts": [{"from_channel": "ecommerce", "to_channel": "pos", "share": "0.5"}],
            },
        ],
    }
    r = c.post(f"{API}/lab", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["baseline"]["collection"]["amount"] == "3500.50"  # M1 only; M2's 99,999 excluded
    base = next(s for s in out["scenarios"] if s["name"] == "base")
    legacy = c.post(f"{API}/growth", json={**PERIOD, "volume_growth": 0.15}).json()
    assert base["collection"] == legacy["projection"]["projected_collection"]
    amb = next(s for s in out["scenarios"] if s["name"] == "ambitious")
    assert sum(x["amount"]["centimes"] for x in amb["bridge"]) == amb["delta"]["centimes"]
    with Session(seeded) as s:
        kinds = [row.assumptions.get("kind") for row in s.scalars(select(ScenarioRunRow))]
        assert kinds.count("scenario_lab") == 3


def test_lab_validation(login):
    c = login()
    bad = [
        {"name": "wild", "volume_growth": "0.1"},
        {"name": "base", "volume_growth": "0.1", "extra": 1},
        {"name": "base", "shifts": [{"from_channel": "pos", "to_channel": "pos", "share": "0.1"}]},
        {"name": "base", "shifts": [{"from_channel": "pos", "to_channel": "bank_transfer", "share": "0.1"}]},
    ]
    for scenario in bad:
        assert c.post(f"{API}/lab", json={**PERIOD, "scenarios": [scenario]}).status_code == 422, scenario
    empty = c.post(
        f"{API}/lab",
        json={"baseline_from": "2026-09-01", "baseline_to": "2026-09-30", "scenarios": [{"name": "base"}]},
    )
    assert empty.status_code == 422  # no accepted activity: no fake baseline
