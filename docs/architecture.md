# Architecture

> Diagrams use [Mermaid](https://mermaid.js.org/). They render on GitHub/GitLab and in VS Code's
> Markdown preview (install the "Markdown Preview Mermaid Support" extension if needed).

## 1. Style
- **Modular monolith**: one deployable, with modules split by bounded context. It's simpler to build,
  test and demo than microservices. A context can be extracted later because contexts only talk
  through ports.
- **Clean Architecture per context**: `api → application → domain ← infrastructure`.
- **DDD tactical patterns**: value objects, aggregates, repositories, domain services.
- **Dependency injection**: FastAPI `Depends` + one composition root (`app/container.py`).

### System view

```mermaid
flowchart LR
    user(["Merchant<br/>browser · mobile"])

    subgraph FE["Frontend · Vite + React · :5173"]
        pages["Feature pages<br/>dashboard · transactions · …"] --> hooks["TanStack Query hooks<br/>features/*/api.ts"]
        hooks --> client["api/client.ts<br/>types generated from OpenAPI"]
    end

    subgraph BE["Backend · FastAPI · :8000"]
        routers["Routers /api/v1"] --> root["container.py<br/>composition root"]
        root --> contexts["Bounded contexts<br/>identity · ledger · analytics · alerts · simulation"]
    end

    db[("PostgreSQL 16<br/>host port 5433")]
    wb[/"data/source/*.xlsx<br/>challenge workbook"/]
    seed["python -m app.seed.reset<br/>deterministic seed"]

    user --> pages
    client -- "JSON + httpOnly cookie<br/>(Vite proxy /api)" --> routers
    contexts -- "SQLAlchemy 2 · Alembic" --> db
    wb --> seed --> contexts
```

## 2. Bounded contexts

| Context | Type | Owns | Key objects |
|---|---|---|---|
| identity | supporting | users, merchant access, profile | `User`, `Merchant`, `ResolveScope` → `MerchantScope` |
| ledger | core | transactions, imports, provenance | `Transaction` (immutable), `ImportBatch`, `ImportTransactions` |
| analytics | core | KPIs, collections, comparisons | `compute_kpis`, `collection_series`, `compare`, `GetDashboard` |
| alerts | core | rules, alert lifecycle | `Alert` aggregate, `AlertRule` strategies |
| simulation | core | growth what-if | `Baseline`, `Assumptions`, `simulate` |
| loyalty | supporting | hypothetical programme versions, offer simulator, pilot points ledger | `ProgramRules`, `simulate`, `break_even`, `plan_accrual`, `LedgerEntry` |
| customers | supporting | pseudonymous customer analytics, win-back decisions (reads ledger via `TransactionReader`) | `build_book`, `CustomerProfile`, `return_status`, `reengagement_list`, `RecordDecision` |

### Context map
Arrows mean "depends on". Analytics and alerts *conform* to the ledger's published `Transaction`
model (read only). Nothing depends on alerts or simulation, so they can be built in parallel.

```mermaid
flowchart TB
    subgraph SK["Shared kernel · app/shared/domain"]
        vo["Money · DateRange · Rate<br/>MerchantScope · TransactionStatus · Channel"]
    end

    identity["identity<br/>User · Merchant · access"]
    ledger["ledger<br/>Transaction · ImportBatch"]
    analytics["analytics<br/>KPIs · period comparison"]
    alerts["alerts<br/>Alert aggregate · rules"]
    simulation["simulation<br/>growth what-if"]

    identity -. "produces MerchantScope<br/>(ResolveScope)" .-> vo
    analytics -- "conformist:<br/>reads Transaction" --> ledger
    alerts -- "RuleContext holds<br/>Transaction lists" --> ledger
    alerts -- "rules reuse<br/>compute_kpis" --> analytics
    simulation -- "Baseline.from_kpis" --> analytics

    ledger --> vo
    analytics --> vo
    alerts --> vo
    simulation --> vo
```

## 3. The dependency rule (non-negotiable)

```mermaid
flowchart LR
    api["api/<br/>routers · Pydantic schemas"]
    app["application/<br/>use cases · ports (Protocols)"]
    dom["domain/<br/>entities · value objects · pure functions"]
    infra["infrastructure/<br/>SQLAlchemy repos · file readers · JWT · Argon2"]
    root["app/container.py<br/>composition root"]

    api --> app --> dom
    infra --> dom
    infra -. "implements ports" .-> app
    api -- "Depends(get_…)" --> root
    root -- "instantiates" --> infra
    root -- "instantiates" --> app

    style dom fill:#ccfbf1,stroke:#0f766e,stroke-width:2px
    style root fill:#fef3c7,stroke:#b45309
```

The domain is in the centre and imports nothing framework-related. Only `container.py` knows
which concrete adapter backs each port.

| Layer | May import | Must NOT import |
|---|---|---|
| `domain/` | `app.shared.domain`, other contexts' `domain` | FastAPI, SQLAlchemy, Pydantic, `app.db` |
| `application/` | `domain`, its own `ports.py` | FastAPI, SQLAlchemy |
| `infrastructure/` | everything above + SQLAlchemy, `app.db.models` | `api/` |
| `api/` | `application`, `app.container`, Pydantic | `infrastructure` directly (go through `container.py`) |

Quick check: `grep -rn "sqlalchemy\|fastapi" src/backend/app/contexts/*/domain` must return nothing.

## 4. Shared kernel (`app/shared/domain`)

| Value object | Why it exists |
|---|---|
| `Money` | integer centimes, DZD. Makes float rounding bugs impossible |
| `DateRange` | half-open `[start, end)`. `previous()` gives the like-for-like prior period |
| `Rate` | keeps numerator and denominator together. `value` is `None` when the denominator is 0 |
| `MerchantScope` | authorized tenant. **Every repository read takes it as the first argument** |
| `TransactionStatus` / `Channel` | enums with tolerant EN/FR parsing. `is_collected` is true only for Accepted |

```mermaid
classDiagram
    class Money {
        +int centimes
        +str currency = "DZD"
        +of(value) Money
        +total(items) Money
        +scale(factor) Money
        +average_over(parts) Money | None
        +to_decimal() Decimal
    }
    class DateRange {
        +date start
        +date end  (exclusive)
        +inclusive(first, last) DateRange
        +previous() DateRange
        +contains(moment) bool
        +days int
    }
    class Rate {
        +int numerator
        +int denominator
        +value Decimal | None
    }
    class MerchantScope {
        +int user_id
        +str merchant_id
        +str role
    }
    class TransactionStatus {
        <<enum>>
        accepted
        declined
        cancelled
        refunded
        +is_collected bool
        +is_authorization_decision bool
    }
    class Transaction {
        <<entity · ledger>>
        +str transaction_id
        +str merchant_id
        +datetime occurred_at
        +Money amount
        +Channel channel
        +TransactionStatus status
        +DataOrigin data_origin
        +str source_batch_id
    }
    Transaction --> Money
    Transaction --> TransactionStatus
```

## 5. Tenant isolation
`get_scope` (in `container.py`) reads the session cookie, then `ResolveScope` loads the user's
grants from `user_merchant_access`. An optional `X-Merchant-Id` header can select among the
user's *own* merchants; anything else returns 403. Repositories filter by `scope.merchant_id`,
so a transaction belonging to another merchant returns **404**, which doesn't reveal that it exists.
Integration tests cover both cases.

### One request, end to end: `GET /api/v1/analytics/dashboard`

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant R as analytics router
    participant C as container.py
    participant S as ResolveScope
    participant UC as GetDashboard
    participant Repo as SqlTransactionRepository
    participant K as analytics domain
    participant DB as PostgreSQL

    B->>R: GET /analytics/dashboard?date_from&date_to (cookie mp_session)
    R->>C: resolve Depends(get_scope), Depends(get_dashboard_uc), Depends(get_today)
    C->>C: JwtTokenService.decode(cookie) gives user_id
    alt missing or invalid token
        C-->>B: 401 Not authenticated
    end
    C->>S: execute(user_id, X-Merchant-Id header)
    S->>DB: SELECT grants FROM user_merchant_access
    alt merchant not granted
        S-->>B: 403 Forbidden
    end
    S-->>C: MerchantScope(user_id, merchant_id, role)
    C-->>R: GetDashboard(SqlTransactionRepository(session))
    R->>UC: execute(scope, period, granularity)
    UC->>Repo: list_in_period(scope, period) and previous period
    Repo->>DB: SELECT WHERE merchant_id = scope.merchant_id AND occurred_at in half-open period
    Repo-->>UC: list of Transaction (domain objects)
    UC->>K: compute_kpis, compare, collection_series, channel_mix
    K-->>UC: KpiSnapshot, PeriodChange, SeriesPoint, ChannelShare
    UC-->>R: Dashboard
    R-->>B: 200 DashboardOut JSON (MoneyOut, RateOut)
```

## 6. Dependency injection

### Ports and adapters
Use cases depend on **Protocols** (ports). One SQL adapter implements several ports through
structural typing, and tests use in-memory fakes in its place.

```mermaid
classDiagram
    direction LR
    class TransactionRepository {
        <<Protocol · ledger port>>
        +search(scope, flt, page) TransactionPage
        +get(scope, transaction_id) Transaction
    }
    class TransactionWriter {
        <<Protocol · ledger port>>
        +existing_ids(ids) set
        +save_batch(batch, transactions)
    }
    class TransactionReader {
        <<Protocol · analytics port>>
        +list_in_period(scope, period) list
    }
    class SqlTransactionRepository {
        <<adapter · infrastructure>>
    }
    class FakeWriter {
        <<test double>>
    }
    class SearchTransactions {
        <<use case>>
    }
    class ImportTransactions {
        <<use case>>
    }
    class GetDashboard {
        <<use case>>
    }

    SearchTransactions --> TransactionRepository
    ImportTransactions --> TransactionWriter
    GetDashboard --> TransactionReader
    SqlTransactionRepository ..|> TransactionRepository
    SqlTransactionRepository ..|> TransactionWriter
    SqlTransactionRepository ..|> TransactionReader
    FakeWriter ..|> TransactionWriter
```

```python
# container.py: the only place that knows concrete classes
def get_transaction_repository(db=Depends(get_db)) -> SqlTransactionRepository: ...
def get_dashboard_uc(repo=Depends(get_transaction_repository)) -> GetDashboard:
    return GetDashboard(repo)          # analytics port <- ledger adapter

# router
def dashboard(scope=Depends(get_scope), uc: GetDashboard = Depends(get_dashboard_uc)): ...

# tests
app.dependency_overrides[get_today] = lambda: date(2026, 11, 20)
```

`get_today` is an injectable clock, so the demo and tests are reproducible.

## 7. Data model

The full schema is created by the first migration (`a21993cae9cd`), including the tables the team
has not wired yet (alerts, scenario runs, audit events). The seven original source fields live
unchanged in `transactions`; `data_origin` and `source_batch_id` are provenance metadata.

```mermaid
erDiagram
    USERS ||--o{ USER_MERCHANT_ACCESS : "is granted"
    MERCHANTS ||--o{ USER_MERCHANT_ACCESS : "grants"
    MERCHANTS ||--o{ TRANSACTIONS : "owns"
    IMPORT_BATCHES ||--o{ TRANSACTIONS : "provenance of"
    MERCHANTS ||--o{ ALERTS : "raises"
    MERCHANTS ||--o{ SCENARIO_RUNS : "simulated for"
    USERS ||--o{ SCENARIO_RUNS : "created by"

    USERS {
        int id PK
        string email UK
        string password_hash
        string status
    }
    MERCHANTS {
        string merchant_id PK
        string display_name
        string category
        string timezone
        string operating_days
        bigint monthly_goal_centimes
    }
    USER_MERCHANT_ACCESS {
        int user_id PK, FK
        string merchant_id PK, FK
        string role
    }
    IMPORT_BATCHES {
        string batch_id PK
        string source_name
        string data_origin
        datetime imported_at
        int row_count
    }
    TRANSACTIONS {
        string transaction_id PK
        string merchant_id FK
        datetime occurred_at
        bigint amount_centimes
        string channel
        string status
        string category
        string data_origin
        string source_batch_id FK
    }
    ALERTS {
        int id PK
        string merchant_id FK
        string rule_code
        string severity
        date window_start
        date window_end
        numeric observed_value
        numeric baseline_value
        numeric delta_pct
        text explanation
        text evidence_ref
        string state
        string dedupe_key UK
    }
    SCENARIO_RUNS {
        int id PK
        string merchant_id FK
        int created_by FK
        date baseline_start
        date baseline_end
        json assumptions
        int projected_count
        bigint projected_collection_centimes
    }
    AUDIT_EVENTS {
        int id PK
        int actor_id
        string action
        string entity_ref
        datetime created_at
    }
```

`transactions` has a composite index on `(merchant_id, occurred_at)`, which serves every scoped,
period-filtered query.

## 8. Key flows

### Import pipeline (workbook and synthetic seed share it)

```mermaid
flowchart LR
    xlsx[/"xlsx · csv<br/>data/source/"/] --> read["file_sources.read_any<br/>HEADER_ALIASES → canonical keys"]
    synth["synthetic_demo.generate_rows<br/>fixed seeds 42 · 43"] --> uc
    read --> uc["ImportTransactions.execute"]
    uc --> parse["row_parsing.parse_row<br/>required fields · date · amount > 0<br/>status / channel aliases"]
    parse --> dup{"duplicate in file<br/>or already imported?"}
    parse -- "row errors" --> report
    dup -- "yes" --> report["ImportReport<br/>row-level errors<br/>NOTHING saved"]
    dup -- "no, and zero errors" --> save["ensure merchants exist<br/>save ImportBatch + rows<br/>data_origin · source_batch_id"]
    save --> ok["ImportReport ok<br/>batch_id · imported_rows"]

    style report fill:#ffe4e6,stroke:#be123c
    style ok fill:#ccfbf1,stroke:#0f766e
```

The import is all-or-nothing: if any row fails, the whole batch is rejected with a report, so no
data is ever silently corrupted.

### Alert lifecycle (`Alert` aggregate)

```mermaid
stateDiagram-v2
    [*] --> open: rule fires and dedupe_key is new
    open --> acknowledged: acknowledge()
    open --> resolved: resolve()
    acknowledged --> resolved: resolve()
    resolved --> [*]

    note right of open
        dedupe_key = rule_code + merchant_id + window
        re-running the evaluation never duplicates an alert
    end note
    note left of resolved
        any other transition raises
        InvalidStateTransition, mapped to HTTP 409
    end note
```

### Alert evaluation (Strategy pattern, part of the team plan)

```mermaid
flowchart LR
    trigger["POST /alerts/evaluate<br/>or end of seed"] --> ev["EvaluateAlerts.execute(scope, today)"]
    ev --> ctx["RuleContext<br/>last 14 days vs previous 14<br/>+ monthly goal"]
    ctx --> r1["CollectionDropRule ✔"]
    ctx --> r2["DeclineSpikeRule (TODO)"]
    ctx --> r3["InactivityRule (TODO)"]
    ctx --> r4["GoalReachedRule (TODO)"]
    r1 & r2 & r3 & r4 --> gate{"minimum-sample gate<br/>and threshold met?"}
    gate -- "no" --> none["None (stay quiet)"]
    gate -- "yes" --> alert["Alert with explanation<br/>observed · baseline · delta · evidence_ref"]
    alert --> repo["AlertRepository.save<br/>skip if dedupe_key exists"]
```

## 9. Frontend structure

```mermaid
flowchart TB
    main["main.tsx"] --> qc["QueryClientProvider"] --> rp["RouterProvider (app/router.tsx)"]
    rp --> login["/login · LoginPage"]
    rp --> guard["RequireAuth<br/>GET /merchant/me, 401 → /login"]
    guard --> fp["FilterProvider<br/>global period + granularity"]
    fp --> layout["Layout<br/>sidebar · PeriodPicker · FR/AR switch"]
    layout --> dash["DashboardPage"]
    layout --> tx["TransactionsPage<br/>filters in URL"]
    layout --> other["Collections · Alerts · Simulator<br/>Insights · Profile (placeholders)"]
    dash --> h1["useDashboard"]
    tx --> h2["useTransactions · useTransaction"]
    h1 & h2 --> client["api/client.ts<br/>fetch + cookie"]
    client --> types["api/schema.d.ts<br/>make gen-api"]
    i18n["i18n · fr.json / ar.json<br/>sets dir=rtl for Arabic"] -.-> layout
```

- Server state lives in TanStack Query (no global store). The only client state is the shared
  period filter, plus ledger filters kept in the URL so dashboards and alerts can deep-link
  (`/transactions?status=declined&channel=ecommerce`).
- The frontend never does money arithmetic: it formats the `MoneyOut.amount` string it receives.

## 10. Recipes

### Add an endpoint (example: `GET /collections/summary`)
1. **Domain**: pure function(s) in `analytics/domain/` (reuse `compute_kpis`, `compare`). Add unit tests.
2. **Application**: use case class in `analytics/application/`, taking ports in `__init__`.
3. **Container**: a `get_<use_case>` provider in `app/container.py`.
4. **API**: a Pydantic response model and route in `analytics/api/router.py`, with `scope=Depends(get_scope)`.
5. Wire the router in `app/main.py` if it's a new context.
6. Run `make gen-api`, then use the new type in the frontend.
7. Add an integration test for scoping plus one for the happy path.

### Add an alert rule
1. Create a class in `alerts/domain/rules.py` with `code` and `evaluate(ctx) -> Alert | None`.
2. Include a minimum-sample gate and a human-readable `explanation` (metric, windows, threshold, values).
3. Add it to `DEFAULT_RULES`. No other code changes.
4. Write unit tests: one that fires, one that stays quiet, and one with a small sample.

### Change the schema
Edit `app/db/models.py`, run `cd src/backend && uv run alembic revision --autogenerate -m "..."`,
review the file, and commit it. **Only one person creates migrations at a time** (tell your teammate).

## 11. Deliberately NOT built (and why)
| Pattern | Reason for skipping it during the hackathon |
|---|---|
| Unit of Work abstraction | one SQLAlchemy session per request is already a unit of work |
| Domain event bus | alert evaluation is called directly after import or on demand |
| Generic base repository | explicit, scoped methods make tenant isolation easier to review |
| Microservices | no workload justifies them, and they'd add deployment risk |
| Deep learning / fraud model | 150 rows, no labels (see blueprint §3 and §7) |
