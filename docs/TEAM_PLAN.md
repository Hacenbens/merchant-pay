# Team plan: hackathon day

**Goal:** all six required modules work end to end in the live app, the demo is reproducible from
`make seed`, and there is one honest intelligence feature. Functionality and technical quality are 50% of
the score, so **never trade a mandatory flow for ML**.

## What already exists (scaffold)
| Done | Where |
|---|---|
| Auth (Argon2 + JWT httpOnly cookie), `GET /merchant/me`, tenant scope | `contexts/identity`, `container.get_scope` |
| Workbook/CSV import with row-level report + provenance; ledger search/detail | `contexts/ledger` |
| KPIs, period comparison, `GET /analytics/dashboard` | `contexts/analytics` |
| `Alert` aggregate + `CollectionDropRule`; growth simulator domain | `contexts/alerts/domain`, `contexts/simulation/domain` |
| Full DB schema + migration (alerts, scenario_runs, audit tables included) | `app/db/models.py` |
| Deterministic synthetic hero merchant with planted anomaly | `app/seed/` |
| Frontend: login, dashboard, transactions (+ drawer), FR/AR RTL, global period filter | `src/frontend/src` |
| 33 backend tests (unit + integration incl. cross-tenant) | `src/backend/tests` |

## Roles
- **Person A, backend/data/analytics.** Owns `src/backend`, the seed data and the formulas.
- **Person B, frontend/UX/i18n.** Owns `src/frontend`, accessibility and the demo flow.
- **Both** own the API contract: Pydantic response models are the contract. Agree on a response
  shape *before* coding, and A runs `make gen-api` after every schema change so B gets typed results.

## Phases (time-boxed, with exit gates)
Hours assume a ~14 h working day. Scale them if the event is shorter, and cut from the bottom of the list.

### Phase 0, together (≤ 1 h)
- [ ] Both: `make install && make up seed && make dev-front`, log in, run `make test`.
- [ ] Drop the real workbook into `data/source/`, run `make seed`. If import fails, A adds header aliases in
      `ledger/infrastructure/file_sources.py::HEADER_ALIASES` (the importer prints the found headers).
- [ ] Agree on the response shapes for the Phase 1–2 endpoints (below).
- **Exit gate:** the app runs on both laptops and the workbook is imported.

### Phase 1, core modules (≈ 4 h)
**Person A**
- [x] `PATCH /merchant/me`: `UpdateMerchantProfile` use case + `MerchantRepository.save` + audit event
      (`identity/application/use_cases.py`, `identity/api/router.py`).
- [x] `GET /collections/summary?a_from&a_to&b_from&b_to`: status totals for period A and period B, plus
      per-status `compare()` (`analytics/application/`, `analytics/api/router.py`). Integration test: A total equals the sum of the ledger.
- [ ] Login rate limit (simple in-memory counter per email+IP) in `identity/api/router.py`.

**Person B**
- [x] Collections page (`features/collections/`): period A vs B pickers, status cards, delta badges,
      "see transactions" deep links (`/transactions?status=…`).
- [x] Profile page (`features/merchant/`): show `/merchant/me`, edit form → PATCH, monthly goal input.
- [ ] Dashboard: empty state when `total_count == 0`, a skeleton while loading, and a mobile layout check at 375 px.
- **Exit gate:** modules 01–04 pass the acceptance checklist (bottom of this file).

### Phase 2, alerts and simulator (≈ 4 h)
**Person A**
- [x] `alerts/infrastructure/sql_alert_repository.py` (map `AlertRow` ↔ `Alert`, skip insert on existing `dedupe_key`).
- [x] `EvaluateAlerts` use case: last 14 days vs previous 14, run `DEFAULT_RULES`, save. Also `ListAlerts`,
      `AcknowledgeAlert`, `ResolveAlert`.
- [x] Rules: `DeclineSpikeRule` (decline rate vs baseline, min 20 attempts, show the denominator),
      `InactivityRule` (gap > 3× the merchant's median gap), `GoalReachedRule` (80% / 100% of the monthly goal).
- [x] `alerts/api/router.py`: `GET /alerts`, `POST /alerts/evaluate`, `POST /alerts/{id}/acknowledge|resolve`.
      Register it in `main.py`. Call `EvaluateAlerts` at the end of `app/seed/reset.py` so the demo has alerts.
- [x] `POST /simulations/growth` (`simulation/application/` + `api/`): body `{baseline_from, baseline_to,
      volume_growth, acceptance_change?, ticket_change?}` → baseline, projection and assumptions. Persist a `ScenarioRunRow`.

**Person B**
- [x] Alerts page: tabs open / acknowledged / resolved, a severity badge (strong colour **only** here), a detail
      panel with metric, windows, threshold, observed and baseline values, a link to the evidence in the ledger, and acknowledge/resolve buttons.
- [x] Dashboard: an alert panel (top 3 open alerts).
- [x] Simulator page: volume slider/input (default +15%), advanced assumptions collapsed, a result
      card (projected count, projected collection, Δ DZD, Δ%), an **assumptions panel**, and a reset button.
- **Exit gate:** demo steps 4–6 work live (`docs/demo_runbook.md`).

### Phase 3, differentiation (≈ 3 h, only after the Phase 2 gate)
- [x] A: `analytics/domain/decline_signal.py`, a Beta-Binomial posterior (prior Beta(1, 19) ≈ 5%) giving the
      posterior mean + 90% credible interval, with "insufficient data" below 20 attempts. Endpoint `GET /insights/decline`.
- [x] A+B: high/low activity periods (mandatory, module 04): `GET /analytics/activity` + dashboard card.
- [x] B: Insights page (Collection Opportunity Radar): per-channel declined value, credible intervals, sample size, "insufficient data" state.
- [ ] A (stretch): `solve_for_goal` in the simulator ("+X% volume needed to reach the monthly goal").
- [ ] B: finish the Arabic strings for new pages, then check keyboard navigation and focus states.
- **Exit gate:** each insight explains its method, data and limits, and its fallback works.

### Phase 4, freeze and rehearse (≈ 2 h, NO new features)
- [ ] `make seed` from scratch, then run the full runbook twice and time it.
- [ ] Remove the `PlaceholderPage` usages. No dead buttons.
- [ ] Update the README with screenshots and record a backup video.

## If you're late, cut in this order
1. Monte Carlo / EWMA / ETS / IsolationForest (never started)
2. Goal back-solver
3. Insights page (keep the Beta-Binomial numbers only inside the decline alert explanation)
4. Arabic for the new pages (keep French complete)
5. Login rate limiting

**Never cut:** tenant isolation, status separation, alert explanations, the +15% simulator, or reset/seed.

## Working rules
- **Dependency rule:** no FastAPI or SQLAlchemy in `domain/` or `application/` (see `docs/architecture.md` §3).
- **Every merchant endpoint** has `scope: MerchantScope = Depends(get_scope)`, and every repository read takes `scope` first.
- **Money:** `Money` (centimes) in the backend, and `MoneyOut` in responses. The frontend **formats only** and never sums amounts.
- **New endpoint:** follow the recipe in `docs/architecture.md` §7, then run `make gen-api`.
- **Migrations:** only Person A creates them, after telling B.
- **Git:** branch `feat/<context>-<thing>` (e.g. `feat/alerts-api`), small commits, `make test lint` before
  pushing, rebase on `main` often, and merge at least every 2 h. Never commit `.env` or the workbook.
- **Ownership for conflicts:** A owns `src/backend/**`, B owns `src/frontend/**`. Coordinate before editing the other's area.
- **Blocked for more than 20 min?** Tell your teammate and pick the next task.

## Acceptance checklist (from blueprint §14)
- [ ] A user logs in and sees only their assigned merchant (`demo2` sees different data).
- [ ] The ledger returns correct records for combined date, status and channel filters.
- [ ] The dashboard's accepted gross amount equals the sum of the filtered Accepted rows.
- [ ] Declined, Cancelled and Refunded totals are separate everywhere.
- [ ] The period comparison handles a previous period of zero.
- [ ] The 20% collection-drop alert triggers on the seeded hero merchant.
- [ ] The decline spike alert includes its denominator and baseline.
- [ ] The +15% simulator result is reproducible and shows its assumptions.
- [x] Insights have an insufficient-data fallback.
- [ ] The six-step demo completes after `make seed` with no manual DB edits.
