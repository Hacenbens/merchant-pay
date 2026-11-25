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

**Numerical safeguards**
- Money is stored as integer centimes and converted with `Decimal`, ROUND_HALF_UP. The API returns
  `{amount: "123.45", centimes: 12345}`. The frontend only formats the value; it never computes with it.
- Periods are half-open `[start, end)`. The UI sends inclusive dates and the API converts them.
- Timestamps are merchant-local (Africa/Algiers) with no offset, as in the source workbook.
- Merchant scope and period filters are applied before any KPI is computed.
