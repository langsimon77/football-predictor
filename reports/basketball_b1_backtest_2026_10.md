# Basketball phase B1: EuroLeague and NBL baseline backtest

Date: 24 Oct 2026. Branch `basketball-b1`. Rules fixed beforehand:
`data/audit/preregistration_basketball_b1_2026_10.md` (commit 3c1c7b5, amendment 1 in fc22934,
both before any model was fitted). Settings chosen on the tuning seasons only and committed
(8124465, `data/basketball/b1_settings.json`) before the test seasons were scored once.
Numbers: `data/basketball/b1_results.json`. Reproduce:
`uv run python basketball/data.py`, then `basketball/backtest.py tune` and `test`.

Claim labels: **[V]** Verified, with source. **[E]** Estimate, with basis. **[A]** Assumption.

## 1. Verdict for Lang

| Market | EuroLeague | NBL |
|---|---|---|
| Winner | **Passes** (Elo) | **Passes** (Elo) |
| Handicap | **Passes** (Elo) | **Fails**: its ranges are too narrow (calibration) |
| Total points | **Passes** (points model) | **Fails**: no clear gain over a simple average |

[V: b1_results.json] By the rule fixed beforehand, four markets go forward to the next phases:
EuroLeague winner, handicap and total points, and NBL winner. NBL handicap and totals do not.

In plain words:
- **Both models beat a naive guess in the EuroLeague**, on all three markets, over four seasons
  they never saw (1,293 games).
- **The simple Elo rating was as good as or better than the points model** for picking winners
  and margins in both leagues, so Elo is the one kept for those (the rule keeps the simpler
  model unless the other is clearly better).
- **The NBL is harder**: only 450 test games and 10 clubs, and its home edge is small (home
  teams won 55%, against 63% in the EuroLeague) [V].
- **None of this is compared with the bookmakers** (no free odds; B0-D3), so "passes" means
  "better than a naive guess and honest about its uncertainty", not "beats the market" [V].

## 2. What was built

- **Data** (`basketball/data.py`, summary in `data/basketball/b1_data_summary.json`) [V]:
  regular-season games from the English Wikipedia season articles. Club IDs come from each
  game's Wikipedia link, followed through redirects, so sponsor names land on one club
  (32 EuroLeague clubs, 10 NBL clubs over the seasons used).
  - Seven EuroLeague games are left out because the game box and the season's results grid
    disagree on the score (the rule in the plan). Three of them are BC Žalgiris home games in
    2025/26 where the grid's row looks shifted.
  - NBL articles also hold preseason, cup and finals games; only games under "Round N" headings
    are kept, as the plan says (regular seasons only). So the NBL counts are slightly below the
    plan's table, which came from B0 and included those: tuning 252 games (plan: 261), test
    450 (plan: 451).
  - NBL tip-off times are the venue's local time [E: the median tip-off is 18:30 in Perth and
    19:30 in Auckland, the same evening slots as the east coast; Sydney time would put Perth
    games near 21:00]. This matters only for live locks later.
- **Models** (`basketball/models.py`):
  - **Elo**: each club has one rating; the winner takes points from the loser, more for an
    upset and a wide margin. Chance of a home win = 1 / (1 + 10^(-(home rating + home edge -
    away rating) / 400)). The expected margin is a fixed number of points per rating point.
  - **Points model**: each club has an attack and a defence rating; expected home points =
    league average + home edge + home attack - away defence (and the reverse for away points).
    Recent games count more (weights halve every "half-life" days) and a penalty keeps ratings
    near zero until the games justify them.
  - Around each expected value the forecast is a bell curve whose width was measured on the
    tuning seasons. One bell curve gives every handicap and total line.
- **Backtest** (`basketball/backtest.py`): every game day is forecast from earlier days only.
  Tests in `tests/test_basketball_b1.py` include a check that changing one day's results
  never changes that day's or an earlier forecast [V: test passes].

## 3. Settings chosen on the tuning seasons [V: b1_settings.json]

| League | Elo | Points model |
|---|---|---|
| EuroLeague (1,315 tuning games) | K 30, home edge 100, carry-over 0.5, margin multiplier on; 4.0 points per 100 rating points; margin width 12.0 | half-life 120 days, penalty 10; widths 10.0 (home) and 10.5 (away), correlation 0.31 |
| NBL (252 tuning games) | K 20, home edge 50, carry-over 0.75, margin multiplier on; 4.4 points per 100 rating points; margin width 14.1 | half-life 480 days, penalty 3; widths 11.6 and 10.2, correlation 0.15 |

Four choices sit at the edge of their grid (EuroLeague K and carry-over, NBL home edge and
half-life), so a wider grid might have done a little better [E]. The grids were fixed
beforehand and are not changed now.

## 4. Test results

Measures, in plain words:
- **Log loss** (winner): how surprised the forecast was by the results; lower is better.
- **CRPS** (handicap and total): the typical miss of the whole bell curve, in points; lower is
  better. It rewards being close and being honest about the spread.
- Each check compares two forecasts on the same games: the mean difference and its 95% range
  from 4,000 resamples of whole game days. "Below 0" means the first forecast is better.

### EuroLeague: 2022/23 to 2025/26, 1,293 games [V]

| Check | Comparison | Mean (95% range) | Result |
|---|---|---|---|
| W2 | Winner: points model minus Elo | +0.001 (-0.004 to +0.006) | no clear winner: Elo kept |
| W1 | Winner: Elo minus home-win rate | -0.040 (-0.054 to -0.026) | **pass** |
| H2 | Margin: points model minus Elo | -0.02 (-0.06 to +0.02) | no clear winner: Elo kept |
| H1 | Margin: Elo minus naive | -0.36 (-0.48 to -0.25) | **pass** |
| T1 | Total: points model minus naive | -0.45 (-0.58 to -0.31) | **pass** |
| K1 | Winner calibration slope (0.8 to 1.2) | 0.99 | **pass** |
| K2 | Share inside the 90% range (86% to 94%) | margin 90.3%, total 90.9% | **pass** |
| L | Leakage alarm (pick rate above 78%) | Elo 66.0%, points 65.4%, home side 63.3% | no alarm |

- Average miss: margin 9.1 points (both models); total 13.0 points (points model) against 13.7
  (naive) [V].
- Every test season shows the same order: both models ahead of the naive forecasts [V].

### NBL: 2023/24 to 2025/26, 450 games [V]

| Check | Comparison | Mean (95% range) | Result |
|---|---|---|---|
| W2 | Winner: points model minus Elo | +0.013 (+0.002 to +0.024) | Elo better: Elo kept |
| W1 | Winner: Elo minus home-win rate | -0.036 (-0.061 to -0.010) | **pass** |
| H2 | Margin: points model minus Elo | +0.17 (+0.06 to +0.28) | Elo better: Elo kept |
| H1 | Margin: Elo minus naive | -0.62 (-0.89 to -0.35) | **pass** |
| T1 | Total: points model minus naive | -0.11 (-0.52 to +0.31) | **fail** |
| K1 | Winner calibration slope (0.8 to 1.2) | 0.95 | **pass** |
| K2 | Share inside the 90% range (86% to 94%) | margin 84.9%, total 86.7% | margin **fail**, total pass |
| L | Leakage alarm | Elo 62.4%, points 59.8%, home side 54.7% | no alarm |

- The handicap forecast is better than naive but too confident: its 90% range held only 84.9%
  of results, because the width measured on the tuning seasons (14.1 points) was too narrow
  for 2023/24 to 2025/26 [V]. By the rule, the market fails.
- In 2023/24 Elo's winner forecasts were slightly worse than the plain home-win rate (0.684
  against 0.679); 2024/25 and 2025/26 were better [V]. Small seasons swing.

### Regulation time (reported, not judged) [V]

About 4% of games were level after four quarters (EuroLeague 56 of 1,293; NBL 19 of 449). On
regulation-time scores the points model still beats the naive forecasts for the winner and
margin in both leagues, and for the total in the EuroLeague only; NBL margin coverage is again
too low (84.9%). So if Galsport settles at the end of normal time, the picture is the same.

## 5. What this means and what comes next

1. **EuroLeague is ready for the next phases on all three markets; the NBL only for the winner.**
2. **The NBL handicap may be fixable** with a width that follows recent seasons, but that is a
   new rule and must be tested on games it has not seen (B2), not adjusted now.
3. **No market benchmark.** Bookmakers' prices are probably much sharper than these naive
   forecasts [E: in football the bookmakers beat the goals model on 13,038 matches]. Comparing
   with Gal's prices when Lang types them (B0-D3) is the real test.
4. **Next phases (each needs Lang's approval):** B2 challengers (tree models and others, plus
   the NBL width idea), then B4 live run and Model Lab. The NBA waits for B0-D2 (its lock rule).

## 6. Limits

- Wikipedia data: about 0.2% of EuroLeague games disagree between two parts of Wikipedia and
  are left out; the NBL has no second source, so an error there would go unnoticed [V].
- Only final scores, quarter scores and dates are used: no player, injury or travel data.
- Settings at the edge of their grids (section 3).
