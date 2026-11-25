# Metric definitions (single source: `analytics/domain/kpis.py`)

**Accounting rule.** Only `Accepted` contributes to collected money. `Declined` and `Cancelled` are
not collections. `Refunded` is shown separately, because the source has no link from a refund back to
the original sale, so it is never netted against collections.

| Metric | Formula | Notes |
|---|---|---|
| Total transaction count | `COUNT(rows)` | always shown with the status breakdown |
| Gross accepted collection | `SUM(amount WHERE status = Accepted)` | primary collected amount |
| Declined / Cancelled / Refunded amount | `SUM(amount WHERE status = X)` | each shown separately |
| Average accepted ticket | `gross accepted / accepted count` | `null` when accepted count = 0 |
| Acceptance rate | `Accepted / (Accepted + Declined)` | numerator and denominator are always returned |
| Decline rate | `Declined / (Accepted + Declined)` | same denominator |
| Period change | `(current − previous) / previous` | previous = 0 → `new_activity` or `no_activity`, never infinity |
| Channel count share | `channel count / total count` | never mixed with amount share |
| Channel amount share | `channel accepted amount / total accepted amount` | |
| Simulator baseline acceptance share | `Accepted / all initiated` | makes `count × share × ticket` equal the gross collection |

| Weekday activity | `SUM(accepted amount on weekday d) / occurrences of d in the period` | normalised: a 30-day window can hold 5 Mondays and 4 Sundays |
| Busiest / quietest days | top / bottom 3 days by accepted amount | zero-activity days are included in "quietest" |
| Peak hour | hour with the most accepted transactions | weekday/hour pattern shown only with ≥ 30 accepted tx over ≥ 14 days |

**Collection Opportunity Radar (`analytics/domain/decline_signal.py`)**
- Attempts = Accepted + Declined (same denominator as the decline rate). Declined value = `SUM(amount WHERE Declined)`.
  It is *declined transaction value*, never "recoverable revenue" or "loss".
- Prior `Beta(1, 19)` (≈ 5 %, worth 20 pseudo-attempts). Posterior `Beta(1 + declined, 19 + accepted)`.
  Displayed: posterior mean and 90 % credible interval (5th–95th percentile).
- Comparison with the previous equal-length window: exact `P(p_current > p_previous)` (closed form, Evan Miller).
  **Elevated** ≥ 95 %, **Lower** ≤ 5 %, otherwise **No clear change**.
- **Insufficient data** whenever either window has < 20 attempts, whatever the probability says.
- Describes *where* declines concentrate, not *why*: the source has no decline reason.

**Merchant Pulse (`analytics/domain/pulse.py`)**: fixed rules, every number is a stored metric.
| Item | Rule |
|---|---|
| Collection up / down / stable | accepted collection vs the previous equal-length window; "stable" when the change is within ±5 % |
| What explains the gap | exact split `Δ = (n₁ − n₀)·t₀ + n₁·(t₁ − t₀)`: volume effect + average-ticket effect (the ticket effect is computed as the remainder, so the two always sum to Δ to the centime) |
| Declines | the Radar's overall verdict; a channel is named when it holds ≥ 50 % of declined value, together with *its own* verdict (so a small channel stays "insufficient data") |
| Monthly goal pace | month-to-date accepted (1st → today) vs a linear pace `goal × day / days_in_month`; "needed per day" = remaining ÷ days left |

**Customer loyalty intelligence (`customers/domain/profiles.py`, `winback.py`)**: synthetic pseudonymous fixture only.
Only *Accepted* transactions with a `customer_token`. Window W = last `window_days` (default 180) up to today.
| Metric | Definition |
|---|---|
| Coverage | tokenised accepted tx in W / all accepted tx in W (always displayed) |
| Eligible customers | customers with ≥ 1 accepted tx in W; < 20 → "insufficient history" |
| Recency R | days since the last accepted purchase |
| Frequency F | accepted tx in W |
| Historical accepted value M | accepted amount in W. **Not profit, not lifetime value.** Refunds are not subtracted (no link to the original sale) |
| Repeat rate | customers with F ≥ 2 / eligible customers |
| New vs returning (period P) | new = first-ever accepted purchase in P; returning = bought before P and again in P |
| Segments (segments-v1) | New (1 purchase, < 30 d) · One-time (1 purchase, older) · Lapsed · At-risk (from win-back) · Loyal (F ≥ 4 over ≥ 60 d) · Active (other repeat) |
| High value | a flag, never a segment: M strictly above the 80th percentile (nearest rank) of eligible customers; null below 20 customers |

**Win-back radar (winback-v1)**: heuristic risk band, **not a probability**.
Baseline = median gap between distinct purchase days: personal with ≥ 2 intervals, else pooled over the
merchant's repeat customers (≥ 20 intervals), else "insufficient history". Spread σ = 1.4826 × MAD.
For the current gap g: watch ≥ max(1.5·m, m + 2σ, 7 d); at risk ≥ max(2.5·m, m + 4σ, 14 d); lapsed ≥ max(4·m, 60 d).
Single-purchase customers are "not repeat" (no rhythm to drift from). Suggestions (reengage-v1): at-risk +
high value → personal follow-up; at-risk → general offer; watch → no action yet (re-check date shown);
lapsed → low-priority offer. Nothing is sent automatically.

**Loyalty Rewards Studio (`loyalty/domain/`)**: hypothetical programme, assumptions shown next to results.
| Quantity | Definition |
|---|---|
| Points (per accepted, tokenised tx) | `floor(amount / 100 DZD) × points_per_100` if amount ≥ minimum spend; capped per customer per version |
| Reward rate | `points_per_100 × point_value / 100 DZD` (face value returned per DZD) |
| Baseline S | accepted value of tokenised customers in the window (default 90 days) |
| Points issued P(u) | Σ customers `min(cap, floor(points_c × (1 + u)))`: uplift spread proportionally |
| Reward liability | P(u) × point value (face value) |
| Expected reward cost | redemption rate × liability (redemption is an **assumption**) |
| Reward cost on existing sales | redemption rate × P(0) × point value: rewards paid on sales you already had |
| Total cost | reward cost + fixed campaign cost |
| Gross contribution | margin × u × S, **only** with a merchant-entered margin |
| Net scenario contribution | gross contribution − total cost. A scenario result, not accounting profit |
| Break-even uplift | smallest u ≤ 1000 % with margin × u × S ≥ redemption × P(u) × point value + fixed cost (0.1-pt grid, then bisection to 0.1 ‰); also as extra DZD and extra transactions at the average ticket |

**Pilot points ledger**: immutable entries; balance = Σ entries. Idempotency key `earn:v{version}:{transaction_id}`
(unique per merchant in the database), so re-runs, re-imports and retries never double-reward. Expiry writes
an `expire` entry once `expiry_days` pass. Refunds never reverse points (no reliable refund→sale link).
Redemptions are not in the data, so they exist only as a simulator assumption.

**Numerical safeguards**
- Money is stored as integer centimes and converted with `Decimal`, ROUND_HALF_UP. The API returns
  `{amount: "123.45", centimes: 12345}`. The frontend only formats the value; it never computes with it.
- Periods are half-open `[start, end)`. The UI sends inclusive dates and the API converts them.
- Timestamps are merchant-local (Africa/Algiers) with no offset, as in the source workbook.
- Merchant scope and period filters are applied before any KPI is computed.
