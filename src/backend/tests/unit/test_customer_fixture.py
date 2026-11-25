"""The synthetic customer fixture: ledger untouched, tokens stable, planted story recoverable."""

from collections import Counter
from datetime import date

from app.contexts.customers.domain.profiles import build_book
from app.contexts.customers.domain.winback import ReturnStatus
from app.contexts.ledger.domain.row_parsing import parse_row
from app.seed.synthetic_demo import HERO, SECOND, _ledger_rows, customer_population, generate_rows
from app.shared.domain.enums import DataOrigin


def test_ledger_is_unchanged_by_the_fixture_and_tokens_are_stable():
    plain = [r for _, r in _ledger_rows(HERO)]
    enriched = [dict(r) for _, r in generate_rows(HERO)]
    assert [{k: v for k, v in r.items() if k != "customer_token"} for r in enriched] == plain
    again = [r.get("customer_token") for _, r in generate_rows(HERO)]
    assert again == [r.get("customer_token") for r in enriched]
    assert not any("customer_token" in r for _, r in generate_rows(SECOND))  # 2nd merchant: none


def test_tokens_pass_the_import_guard_and_coverage_is_partial():
    parsed = [parse_row(r, n, data_origin=DataOrigin.SYNTHETIC_DEMO) for n, r in generate_rows(HERO)]
    assert all(not errors for _, errors in parsed)
    tokens = [t.customer_token for t, _ in parsed]
    share = sum(1 for t in tokens if t) / len(tokens)
    assert 0.80 < share < 0.90  # walk-ins outside the programme stay untokenised


def test_planted_drift_is_recovered_without_using_the_labels():
    """Ground truth is only read here, after the analysis ran on the ledger alone."""
    txs = [parse_row(r, n, data_origin=DataOrigin.SYNTHETIC_DEMO)[0] for n, r in generate_rows(HERO)]
    status = {p.token: p.evidence.status for p in build_book(txs, date(2026, 11, 20)).profiles}
    planted = [c.token for c in customer_population(HERO) if c.planted_drift]
    found = Counter(status[t] for t in planted)
    assert len(planted) == 14
    assert found[ReturnStatus.AT_RISK] + found[ReturnStatus.WATCH] == 14
    assert found[ReturnStatus.AT_RISK] >= 10
