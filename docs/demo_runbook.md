# Demo runbook (6 official steps)

## Before the jury
```bash
make up seed                                   # clean, deterministic state
cp src/frontend/.env.example src/frontend/.env.local   # VITE_DEMO_TODAY=2026-11-20 (API: DEMO_TODAY)
make dev-front
```
- Log in once as `demo@merchantpay.test` / `demo1234` to warm the caches.
- Keep screenshots or a screen recording of the happy path in case connectivity fails.
- If anything breaks mid-demo, run `make seed` (about 5 s) and log in again.
- Login is throttled after 5 failed attempts (15 min). If you lock yourself out, `docker compose restart backend` clears it.

## Script
| # | Do live | Point out |
|---|---|---|
| 1 | Log in as the demo merchant | The dashboard is scoped to *Épicerie Démo Boumerdès*. Log in as `demo2` to show different data (tenant isolation). |
| 2 | Transactions: search an ID, combine status, channel and dates, open the detail | The detail shows the data origin and import batch (provenance). |
| 3 | Collections: pick the last 14 days and compare with the previous 14 | Accepted vs declined, cancelled and refunded stay separate. The total matches the filtered ledger. |
| 4a | Dashboard, period 7–20 Nov: read the **Merchant Pulse** | −50.9 % (−260,218.78 DZD). Explained by volume (−281,006.14) partly offset by a higher basket (+20,787.36): the parts sum exactly. Goal 32.5 % of 1.5 M DZD, 101,290 DZD/day needed. |
| 4b | Insights, same period | Accepted collection 251,356.50 DZD vs 511,575.28 DZD (−50.9 %). Radar, all channels: **Elevated**, 10/74 vs 6/148, P(higher) = 98.8 %. E-commerce holds 43,256 of 54,905 DZD declined, but with only 17 attempts it is honestly marked **Insufficient data**. That is the sample-size guard working. |
| 4c (optional, 45 s) | Clients → Reconquête | 22 at-risk customers hold 18.1 % of historical tokenised value (1,036,453.66 DZD). The top ones are high-value regulars silent 22–25 days against a 6–8 day rhythm (evidence shown per customer). Log in as `demo2`: "no customer identifier", so nothing is invented. Say it: the tokens are synthetic and planted, and the rule recovers 14/14 planted drifters as at-risk or watch without seeing the labels. |
| 5 | Alerts: open `COLLECTION_DROP`, acknowledge it | A persisted alert with metric, windows, threshold, values and a link to the evidence. |
| 6 | Simulator: +15% volume | Projected count and collection, the delta, and the assumptions panel. |
| 6b (optional, Q&A) | Fidélité: margin 25 %, fixed cost 20,000 DZD, defaults otherwise → Calculate | 1 % back on 2.68 M DZD of identified sales. Base scenario (+3 %, 50 % redemption): **−13,494.99 DZD**, because 97 % of the reward cost rewards sales the merchant already had. Break-even needs **+5.1 %** sales (≈ 35 extra transactions). Save → Run pilot twice: 26,421 points, the second run adds 0 (idempotent). |

## Likely questions
See blueprint §16: why no deep learning, refund treatment, and whether the data is real (it is synthetic).
