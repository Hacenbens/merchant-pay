# Merchant Pay: Intelligent Merchant Financial Management

> **FINOVIA × ENSM × SATIM challenge.** A merchant-facing web app that turns electronic payment
> records into reliable collection visibility, explainable alerts and transparent growth scenarios.

**Design thesis:** make the financial core *boringly correct* and the intelligence *unusually
honest*. Every KPI reconciles with the ledger, every alert shows its evidence, and every scenario
shows its assumptions. Full specification: [`docs/blueprint.pdf`](docs/blueprint.pdf).

## Contents
1. [Quickstart](#1-quickstart)
2. [Module status](#2-module-status)
3. [Where do I find…?](#3-where-do-i-find)
4. [Repository map](#4-repository-map)
5. [Backend map](#5-backend-map)
6. [Frontend map](#6-frontend-map)
7. [API endpoints](#7-api-endpoints)
8. [Commands](#8-commands)
9. [Documentation index](#9-documentation-index)
10. [Team and workflow](#10-team-and-workflow)
11. [Data and security policy](#11-data-and-security-policy)
12. [Tech stack and license](#12-tech-stack-and-license)

---

## 1. Quickstart

**Prerequisites:** Docker, [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
make install                                          # backend (uv) + frontend (npm) dependencies
make up seed                                          # Postgres + API on :8000, then load demo data
cp src/frontend/.env.example src/frontend/.env.local  # freezes "today" at 2026-11-20 for the demo
make dev-front                                        # web app on http://localhost:5173
```

| URL | What |
|---|---|
| http://localhost:5173 | Web app |
| http://localhost:8000/api/docs | Interactive API docs (Swagger) |
| http://localhost:8000/health | Health check |
| `localhost:5433` | PostgreSQL (`merchantpay` / `merchantpay`). Port 5433 avoids clashing with a local Postgres. |

Both clocks are frozen at **2026-11-20**, the last day of data: the web app via `VITE_DEMO_TODAY`, the
API via `DEMO_TODAY` (set in `docker-compose.yml`). That keeps KPIs, alert windows and the simulator
reproducible; override `DEMO_TODAY` to evaluate against the real date.

**Challenge workbook:** drop `Inventory_Report_Template.xlsx` into `data/source/` and run `make seed`
again. The importer prints a row-by-row report if anything is invalid.

### Demo accounts (synthetic data only, password `demo1234`)

| Email | Merchant | Use it to show |
|---|---|---|
| `demo@merchantpay.test` | `M-DEMO-01` Épicerie Démo Boumerdès | main demo: ~2,150 transactions with a planted collection drop and decline spike on 7–20 Nov |
| `demo2@merchantpay.test` | `M-DEMO-02` Restaurant Démo | tenant isolation (sees different data) |
| `owner@merchantpay.test` | first merchant of the workbook | real challenge data (only after the workbook is imported) |

---

## 2. Module status

The six required modules from the blueprint, with where each one lives.
✅ done · 🟡 domain logic written, API/UI to do · ⬜ to do. Tasks: [`docs/TEAM_PLAN.md`](docs/TEAM_PLAN.md).

| # | Module | Backend | Frontend | Status |
|---|---|---|---|---|
| 01 | Merchant management (login, profile, access) | `contexts/identity` | `features/auth`, `features/merchant` | ✅ login, scope, profile view + owner-only validated edit (audited) |
| 02 | Transaction ledger (search, filters, detail) | `contexts/ledger` | `features/transactions` | ✅ |
| 03 | Collection engine (status-separated totals, A vs B) | `contexts/analytics` | `features/collections` | ✅ `/collections/summary` + page |
| 04 | Dynamic dashboard | `contexts/analytics` | `features/dashboard` | ✅ incl. high/low activity periods (`/analytics/activity`) |
| 05 | Alerts and recommendations | `contexts/alerts` | `features/alerts` | ✅ 4 rules, dedupe, transitions, page, dashboard panel |
| 06 | Commercial growth simulator (+15%) | `contexts/simulation` | `features/simulator` | ✅ API, scenario audit, page with assumptions |
| ★ | Collection Opportunity Radar (Beta-Binomial decline signal) | `contexts/analytics` | `features/insights` | ✅ |
| — | Import, provenance, demo seed | `contexts/ledger`, `app/seed` | — | ✅ |

Backend paths are relative to `src/backend/app/`; frontend paths to `src/frontend/src/`.

---

## 3. Where do I find…?

| I want to… | Go to |
|---|---|
| change a **KPI formula** | `src/backend/app/contexts/analytics/domain/kpis.py` and [`docs/metric_definitions.md`](docs/metric_definitions.md) |
| add an **alert rule** | `src/backend/app/contexts/alerts/domain/rules.py` (add a class, register it in `DEFAULT_RULES`) |
| change the **simulator math** | `src/backend/app/contexts/simulation/domain/growth.py` |
| add a **backend endpoint** | follow [architecture §10](docs/architecture.md#10-recipes): domain → application → `container.py` → `api/router.py` |
| wire a **use case to its implementation** (DI) | `src/backend/app/container.py` |
| understand **tenant isolation** | `container.py::get_scope` → `contexts/identity/application/use_cases.py::ResolveScope` |
| change the **database schema** | `src/backend/app/db/models.py`, then `alembic revision --autogenerate` |
| fix a **workbook column name** | `src/backend/app/contexts/ledger/infrastructure/file_sources.py::HEADER_ALIASES` |
| change the **synthetic demo data** | `src/backend/app/seed/synthetic_demo.py` |
| change **demo accounts** | `src/backend/app/seed/reset.py` |
| map a **domain error to an HTTP code** | `src/backend/app/shared/api/errors.py` |
| add a **frontend page** | `src/frontend/src/features/<module>/` + route in `src/frontend/src/app/router.tsx` + link in `app/Layout.tsx` |
| call the API from React | a hook in `features/<module>/api.ts` using `api()` from `src/frontend/src/api/client.ts` |
| get **types for a new endpoint** | `make gen-api` → `src/frontend/src/api/schema.d.ts`, then alias in `api/types.ts` |
| add or translate **UI text** | `src/frontend/src/i18n/fr.json` and `ar.json` (same keys in both) |
| format **money / dates / %** | `src/frontend/src/lib/format.ts` |
| reuse a **UI component** | `src/frontend/src/components/` (`Card`, `Button`, `Badge`, `KpiCard`, `StatusBadge`…) |
| change the **global period filter** | `src/frontend/src/app/filters.tsx` |
| write a **backend test** | `src/backend/tests/unit/` (pure domain) or `tests/integration/` (HTTP + DB, fixtures in `conftest.py`) |
| prepare the **jury demo** | [`docs/demo_runbook.md`](docs/demo_runbook.md) |

---

## 4. Repository map

```
.
├── README.md                 ← you are here
├── LICENSE                   MIT
├── Makefile                  every common command (section 8)
├── docker-compose.yml        Postgres (host :5433) + API (:8000)
├── .env.example              backend settings template (copy to .env)
│
├── docs/                     documentation (section 9)
│   ├── TEAM_PLAN.md          who does what, phases, acceptance checklist
│   ├── architecture.md       diagrams, rules, recipes
│   ├── metric_definitions.md financial formulas
│   ├── demo_runbook.md       6-step jury demo
│   └── blueprint.pdf         competition blueprint
│
├── data/
│   ├── source/               challenge workbook goes here (git-ignored)
│   └── synthetic_demo/       reserved for exported synthetic fixtures
│
└── src/
    ├── backend/              Python · FastAPI (section 5)
    └── frontend/             TypeScript · React (section 6)
```

---

## 5. Backend map

`src/backend/` is a modular monolith. Each **bounded context** under `app/contexts/` has the same
four layers, and dependencies only point inward toward `domain/`
([why](docs/architecture.md#3-the-dependency-rule-non-negotiable)):

| Layer | Contains | Allowed to import |
|---|---|---|
| `domain/` | entities, value objects, pure business functions | shared kernel only (no FastAPI or SQLAlchemy) |
| `application/` | use cases + `ports.py` (interfaces as `Protocol`s) | `domain/` |
| `infrastructure/` | SQL repositories, file readers, JWT/Argon2 | everything above + SQLAlchemy |
| `api/` | FastAPI router + Pydantic response models | `application/`, `app/container.py` |

### App-level files

```
src/backend/
├── app/
│   ├── main.py               creates the FastAPI app and registers routers under /api/v1
│   ├── container.py          COMPOSITION ROOT: every Depends() provider, get_scope, get_today
│   ├── config.py             settings from environment variables
│   ├── shared/
│   │   ├── domain/           SHARED KERNEL: money.py · date_range.py · rate.py ·
│   │   │                     merchant_scope.py · enums.py · errors.py
│   │   └── api/              schemas.py (MoneyOut, RateOut, PeriodOut) · errors.py (error → HTTP)
│   ├── db/
│   │   ├── models.py         ALL tables (one file, so there are no migration conflicts)
│   │   ├── session.py        engine + session factory
│   │   └── migrations/       Alembic (versions/a21993cae9cd_initial_schema.py)
│   ├── seed/
│   │   ├── reset.py          `make seed`: wipe → synthetic merchants → workbook → demo users
│   │   ├── synthetic_demo.py deterministic generator (fixed seeds, planted anomaly)
│   │   └── accounts.py       helpers to create merchants and users
│   └── contexts/             bounded contexts (below)
├── tests/
│   ├── unit/                 pure domain tests (fast, no DB)
│   ├── integration/          HTTP + SQLite in-memory, including cross-tenant checks
│   ├── conftest.py           fixtures: seeded DB, client, login()
│   └── factories.py          tx() helper for building transactions
├── pyproject.toml · uv.lock  dependencies, ruff, pytest config
└── Dockerfile · alembic.ini
```

### Bounded contexts, file by file

| Context | `domain/` | `application/` | `infrastructure/` | `api/` |
|---|---|---|---|---|
| **identity** | `model.py`: `User`, `Merchant`, `MerchantAccess`, `Role` | `ports.py`, `use_cases.py`: `Authenticate`, `ResolveScope`, `GetMe` | `security.py`: Argon2, JWT · `sql_repositories.py` | `router.py`: login, logout, `/merchant/me` |
| **ledger** | `transaction.py`: `Transaction` · `row_parsing.py`: validation · `import_batch.py` | `ports.py`, `queries.py`: `SearchTransactions`, `GetTransaction` · `import_transactions.py` | `sql_transaction_repository.py` · `file_sources.py`: xlsx/csv | `router.py`: `/transactions` |
| **analytics** | `kpis.py`: `compute_kpis`, `channel_mix`, `collection_series` · `period_comparison.py` · `activity.py` · `decline_signal.py` + `beta.py` | `get_dashboard.py`: `GetDashboard` · `get_collections.py`: `GetCollectionsSummary` · `get_insights.py`: `GetDeclineRadar`, `GetActivityProfile` | (reuses the ledger SQL repository) | `router.py`: `/analytics/dashboard` · `collections_router.py` endpoints: `/collections/summary` |
| **alerts** | `alert.py`: `Alert` state machine · `rules.py`: `CollectionDropRule`, `DeclineSpikeRule`, `InactivityRule`, `GoalReachedRule` | `ports.py`, `evaluate_alerts.py`, `manage_alerts.py` | `sql_alert_repository.py` (dedupe on `dedupe_key`) | `router.py`: `/alerts` |
| **simulation** | `growth.py`: `Baseline`, `Assumptions`, `simulate` · `scenario_run.py` | `run_simulation.py` | `sql_scenario_repository.py` (audit row) | `router.py`: `/simulations/growth` |

⬜ marks files to create, listed with their exact paths in [`docs/TEAM_PLAN.md`](docs/TEAM_PLAN.md).
`TODO(Person A)` comments in the code mark the same spots.

---

## 6. Frontend map

`src/frontend/src/` is organised **by feature**: one folder per module. Each folder holds a
`<Name>Page.tsx` and an `api.ts` containing the TanStack Query hooks for that module.

```
src/frontend/
├── src/
│   ├── main.tsx              entry: QueryClient + Router + i18n + CSS
│   ├── app/                  APP SHELL
│   │   ├── router.tsx        all routes (add new pages here)
│   │   ├── Layout.tsx        sidebar nav + header (period picker, language, logout)
│   │   ├── RequireAuth.tsx   redirects to /login on 401
│   │   ├── filters.tsx       global period + granularity context, PeriodPicker
│   │   └── LanguageSwitch.tsx
│   ├── api/
│   │   ├── client.ts         fetch wrapper (cookie auth, ApiError)
│   │   ├── schema.d.ts       GENERATED by `make gen-api`, never edit by hand
│   │   └── types.ts          friendly aliases: Dashboard, Transaction, Money…
│   ├── features/
│   │   ├── auth/             ✅ LoginPage · api.ts (useMe, useLogin, useLogout)
│   │   ├── dashboard/        ✅ DashboardPage (KPIs, trend, channels, statuses) · api.ts
│   │   ├── transactions/     ✅ TransactionsPage (filters in URL) · TransactionDrawer · api.ts
│   │   ├── collections/      ✅ CollectionsPage (period A vs B, status cards) · api.ts
│   │   ├── alerts/           ✅ AlertsPage (tabs, detail, ack/resolve) · api.ts · SeverityBadge
│   │   ├── simulator/        ✅ SimulatorPage (+15% default, assumptions) · api.ts
│   │   ├── insights/         ✅ InsightsPage (Collection Opportunity Radar) · api.ts
│   │   └── merchant/         ✅ ProfilePage (owner-only edit, monthly goal)
│   ├── components/
│   │   ├── ui/index.tsx      Card, Button, Badge, Spinner, EmptyState, ErrorState
│   │   ├── KpiCard.tsx · StatusBadge.tsx
│   │   └── PlaceholderPage.tsx  remove before the demo
│   ├── i18n/                 index.ts (switches RTL) · fr.json · ar.json
│   └── lib/format.ts         DZD, %, dates (display only, no money arithmetic)
├── .env.example              VITE_DEMO_TODAY (copy to .env.local)
├── vite.config.ts            dev proxy /api → :8000, alias @ → src
└── package.json · tsconfig.json
```

**Route → page**

| Route | Page | Backend endpoint |
|---|---|---|
| `/login` | `features/auth/LoginPage.tsx` | `POST /auth/login` |
| `/` | `features/dashboard/DashboardPage.tsx` | `GET /analytics/dashboard` |
| `/transactions` | `features/transactions/TransactionsPage.tsx` | `GET /transactions`, `GET /transactions/{id}` |
| `/collections` | `features/collections/CollectionsPage.tsx` | `GET /collections/summary` |
| `/alerts` | `features/alerts/AlertsPage.tsx` | `GET /alerts`, `POST /alerts/evaluate` |
| `/simulator` | `features/simulator/SimulatorPage.tsx` | `POST /simulations/growth` |
| `/insights` | `features/insights/InsightsPage.tsx` | `GET /insights/decline` |
| `/profile` | `features/merchant/ProfilePage.tsx` | `GET /merchant/me` · `PATCH /merchant/me` |

---

## 7. API endpoints

All under `/api/v1`. Every merchant endpoint is scoped server-side by `Depends(get_scope)`.

| Method | Path | Context | Status |
|---|---|---|---|
| POST | `/auth/login` · `/auth/logout` | identity | ✅ |
| GET | `/merchant/me` | identity | ✅ |
| PATCH | `/merchant/me` | identity | ✅ owner-only, audited |
| GET | `/transactions?date_from&date_to&status&channel&q&page&size` | ledger | ✅ |
| GET | `/transactions/{id}` | ledger | ✅ |
| GET | `/analytics/dashboard?date_from&date_to&granularity` | analytics | ✅ |
| GET | `/collections/summary?a_from&a_to&b_from&b_to` | analytics | ✅ |
| GET | `/alerts?state` | alerts | ✅ |
| POST | `/alerts/evaluate` · `/alerts/{id}/acknowledge\|resolve` | alerts | ✅ |
| POST | `/simulations/growth` | simulation | ✅ |
| GET | `/analytics/activity?date_from&date_to` | analytics | ✅ |
| GET | `/insights/decline?date_from&date_to` | analytics | ✅ |

---

## 8. Commands

Run these from the repository root.

| Command | What it does |
|---|---|
| `make install` | install backend and frontend dependencies |
| `make up` / `make down` | start / stop Postgres + API in Docker |
| `make seed` | wipe and reseed the deterministic demo data (+ workbook if present) |
| `make dev-front` | web app with hot reload on :5173 |
| `make dev-back` | API locally with hot reload (run `docker compose up -d db` first, stop the API container) |
| `make test` | backend tests + frontend type-check |
| `make lint` | ruff + tsc |
| `make gen-api` | regenerate frontend API types from the FastAPI schema (no server needed) |
| `make logs` | follow API container logs |

---

## 9. Documentation index

| Document | Read it when… |
|---|---|
| [`docs/TEAM_PLAN.md`](docs/TEAM_PLAN.md) | you start the day, or finish a task and need the next one |
| [`docs/architecture.md`](docs/architecture.md) | you add code: diagrams, dependency rule, DI, data model, recipes |
| [`docs/metric_definitions.md`](docs/metric_definitions.md) | you touch any number shown to the merchant |
| [`docs/demo_runbook.md`](docs/demo_runbook.md) | you rehearse or present |
| [`docs/blueprint.pdf`](docs/blueprint.pdf) | you need the official scope, rubric or rationale |

---

## 10. Team and workflow

### Members

| Member | GitHub |
|---|---|
| iyyad2024 | [github.com/iyyad2024](https://github.com/iyyad2024) |
| houssem2055 | [github.com/houssem2055](https://github.com/houssem2055) |
| mehdibidjed | [github.com/mehdibidjed](https://github.com/mehdibidjed) |
| A-Hex | [github.com/A-Hex](https://github.com/A-Hex) |

### Workflow

- **Ownership:** Person A owns `src/backend/**` and the seed data. Person B owns `src/frontend/**`. Pydantic
  response models are the shared contract, so agree on a response shape before coding it.
- **Branches:** `feat/<context>-<thing>` (e.g. `feat/alerts-api`). Make small commits, run `make test lint`
  before pushing, and merge to `main` at least every 2 hours.
- **Golden rules:**
  1. No FastAPI or SQLAlchemy in `domain/` or `application/`.
  2. Every merchant endpoint uses `Depends(get_scope)`, and every repository read takes `scope` first.
  3. Money is `Money` (integer centimes). The frontend formats amounts and never sums them.
  4. Run `make gen-api` after any API change. Only Person A creates migrations.
  5. Never commit `.env` or the workbook.

---

## 11. Data and security policy

- Synthetic data only. There is no live payment processing and no SATIM or bank connectivity.
- No card PAN, CVV, PIN or OTP is ever stored.
- Every row keeps its `source_batch_id`, and synthetic rows are tagged `data_origin=synthetic_demo`.
- Imports are all-or-nothing, with a row-level error report.
- Tenant scope comes from the server-side access mapping, never from a client-supplied ID.
  Another merchant's record returns 404.
- Passwords are hashed with Argon2. The session is a JWT in an httpOnly, SameSite=Lax cookie.

## 12. Tech stack and license

**Backend:** FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · Pydantic v2 · PyJWT · Argon2 · pytest · ruff · uv
**Frontend:** React 19 · TypeScript 5 · Vite · Tailwind CSS 4 · TanStack Query · React Router · react-i18next (FR / AR, RTL) · Recharts

Licensed under [MIT](LICENSE).
