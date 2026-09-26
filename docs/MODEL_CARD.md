# Model card

A one-page summary of the published forecasts: what they are for, how they were built, how well they did, and where they fall short. Claims are labelled [V] Verified, [E] Estimate, or [A] Assumption.

## What is published

| Market | Model | Since |
|---|---|---|
| Home, draw, away; over/under 1.5, 2.5, 3.5 goals; both teams score | `dc_bayes_v1`: Bayesian hierarchical Dixon-Coles with time decay, shots on target, and promoted-team priors from second-tier form | 25 Sep 2026 |
| Total corners, over 8.5 to 11.5 | `corners_total_poisson_v1` | 25 Sep 2026 |
| Total yellow cards, over 3.5 to 5.5 | `cards_nb_v1`, with an EPL referee effect when the referee is known at lock | 25 Sep 2026 |
| Team news | `news_v1`: your Question Queue answers scale the scoring rates, capped at 12% | 26 Sep 2026 |
| Confidence tiers | `tiers_v1`: High, Medium, Low per market | 26 Sep 2026 |

Shadow models are locked and scored every day but never published: Elo, fast Dixon-Coles, four machine-learning challengers, the stacked ensemble, and the Bayesian model without news.

## Intended use

- Personal forecasts for the Premier League and La Liga, 2026/27, locked 24 to 48 hours before kickoff.
- Learning how well a transparent statistical model can do against the betting market.

Not intended as betting advice. The market is still ahead of this model (below). Betting on these forecasts would be expected to lose money after the bookmaker's margin [E: the model trails even the Friday market].

## Data

- Match results, shots, corners, cards, referees, and odds from football-data.co.uk, 2016/17 to now. Odds are used only to judge the model, never as an input [V].
- Fixtures from openfootball (public domain) and football-data.org [V].
- Team news from you, through the daily GitHub Issue; managers from Wikipedia [V].
- Not used: expected goals history (no compliant source), player data, FPL, Understat [V: `docs/DATA_SOURCES.md`].

## How it was tested

Walk-forward: each past match was forecast using only what was known at its lock time. Settings were chosen on 2021/22 and 2022/23; 2023/24 to 2025/26 were scored once [V: `reports/backtest_phase2_test.md`, `reports/backtest_phase4.md`].

| Home, draw, away, 2,227 test matches | Log loss | RPS |
|---|---|---|
| League base rates | 1.0702 | 0.2289 |
| Elo | 0.9786 | 0.1982 |
| **Published Bayesian model** | **0.9759** | **0.1970** |
| Market, Friday snapshot | 0.9601 | 0.1922 |
| Market, closing | 0.9571 | 0.1912 |

Lower is better. Over/under 2.5 goals: log loss 0.6731 against 0.6647 for the closing market. Corners and cards beat league-average baselines (log score −0.009 and −0.019, both intervals below zero) [V].

## Known limitations

1. **Too timid.** Strong favourites win more often than the model says (calibration slope 1.23; 1 is perfect). No calibration map passed the strict test [V].
2. **Behind the market** by about 0.014 in log loss even at the Friday snapshot [V].
3. **No player data.** Team news is a count of missing starters, with effect sizes that are Assumptions [A], to be tested after 10 gameweeks.
4. **Referees.** La Liga referees are named after our lock; EPL Friday and Saturday referees usually are too [V].
5. **Over/under tiers** separate clearly on only 4 of 11 lines [V].
6. **Early season.** Promoted clubs and clubs with new managers carry wide intervals.

## How it changes

Any change to model structure, features, or code that affects forecasts is proposed in `docs/MODEL_CHANGELOG.md` and waits for your approval. Locked forecasts are never edited: the ledger is hash-chained and append-only.
