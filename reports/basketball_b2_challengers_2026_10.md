# Basketball phase B2: challengers against the B1 models

Date: 25 Oct 2026. Branch `basketball-b1` (this shared folder stays on it). Rules fixed
beforehand: `data/audit/preregistration_basketball_b2_2026_10.md` (commit f43848f). Settings
chosen on the tuning seasons only and committed (9c6dc9f, `data/basketball/b2_settings.json`)
before the test seasons were scored once. Numbers: `data/basketball/b2_results.json`.
Reproduce (on macOS XGBoost needs scikit-learn's OpenMP library, see the script's header):
`basketball/locations.py`, then `basketball/backtest_b2.py tune` and `test`.

Claim labels: **[V]** Verified, with source. **[E]** Estimate, with basis. **[A]** Assumption.

## 1. Verdict for Lang

**One of 42 comparisons passes** (7 challengers x 3 markets x 2 leagues) [V: b2_results.json]:
the points model with a home edge for each club (C7) forecasts **EuroLeague total points**
better than the B1 points model. Everything else stays as B1 chose:

| Market | EuroLeague | NBL |
|---|---|---|
| Winner | Elo (B1); no challenger clearly better | Elo (B1); no challenger clearly better |
| Handicap | Elo (B1); no challenger clearly better | Elo (B1) failed calibration in B1; no challenger passes |
| Total points | **C7 passes**: to be watched on 2026/27 games before live use | B1 failed; no challenger passes |

In plain words:
- **The newer methods do not help with this data.** Random forest, XGBoost, histogram gradient
  boosting (the LightGBM method), a regression model, a small neural network and Kalman-filter
  ratings were all no better than Elo and the points model, and several were clearly worse
  [V]. The neural network was the worst everywhere.
- **Why** [E]: the open data has only dates and scores. Elo and the points model already use
  that information well; the extra inputs (travel, rest, form, season stage) add little, and
  flexible models fit noise when a league has 250 to 1,300 tuning games. Tuning picked the
  smallest, most restrained version of nearly every model, which points the same way [V:
  b2_settings.json].
- **The one gain is small but steady**: C7 lowers the EuroLeague total error measure by 0.054
  points (99% range 0.014 to 0.096) and was better in all four test seasons [V].
- **Better forecasts would need better information** (injuries, line-ups, bookmakers' prices),
  not more complex models [E: the same lesson as football, where the bookmakers beat the goals
  model on 13,038 matches].

## 2. What was built

- **Club locations** (`basketball/locations.py`): each club's home city from its Wikipedia
  infobox and the city's coordinates (CC BY-SA), or the arena's when the city has none; all 42
  clubs are located [V: `data/manual/basketball_club_cities.csv`].
- **Features** (`basketball/features.py`), each from earlier days only [V: tests]: F1 Elo
  difference, F2 points-model margin and total, F3 days since each team's last game in our
  data, F4 the away team's travel distance, F5 recent form (last 5 games against Elo's
  expectation), F6 games played this season; and, for the neural network, each team's last 10
  results.
- **Challengers** (`basketball/challengers.py`), exactly the plan's seven, with the plan's
  grids: C1 regression (GLM), C2 random forest, C3 XGBoost, C4 histogram gradient boosting,
  C5 small neural network on the last 10 results, C6 Kalman-filter ratings, C7 points model
  with a home edge per club. C1 to C5 are refitted at each season start and every 28 days.
- **Backtest** (`basketball/backtest_b2.py`): tune on the tuning seasons, then test once with
  checks A1 (99% range below 0), A2 (better in most test seasons), A3 (calibration) and L
  (leakage alarm). Tests: `tests/test_basketball_b2.py`.
- **Build history** [V: Git log and file times]: the code and settings were committed at 09:11
  and the test stage ran at 09:12 on 25 Oct. Afterwards the working copies of the code files
  were removed from the folder (the commit kept them), most likely by a conversation rewind
  [E]. They were restored from the commit unchanged, and the test stage was run again to check
  it gives the same numbers: every pass and fail and every number matched, except 50 random
  forest (C2) values that differ in the 16th decimal place, from its parallel tree building
  [V]. The first run's file is the one kept.

## 3. Test results (negative = the challenger is better than the B1 model)

Measures: winner, log loss; handicap (margin) and total, CRPS in points. Ranges are 99%
(4,000 resamples of whole game days). "Seasons" counts the test seasons where the challenger
was better. Calibration: the winner slope (0.8 to 1.2), or the share inside the 90% range
(86% to 94%).

### EuroLeague: 2022/23 to 2025/26, 1,293 games [V]

| Challenger | Winner | Handicap | Total |
|---|---|---|---|
| C1 Regression (GLM) | +0.000 (-0.005 to +0.005), 2 seasons | +0.00 (-0.03 to +0.04), 2 | -0.00 (-0.08 to +0.08), 2 |
| C2 Random forest | +0.006 (-0.000 to +0.012), 0 | +0.02 (-0.03 to +0.07), 1 | +0.05 (-0.03 to +0.13), 0 |
| C3 XGBoost | +0.004 (-0.003 to +0.012), 0 | +0.03 (-0.02 to +0.08), 1 | **+0.12 (+0.05 to +0.20), worse** |
| C4 Histogram boosting | +0.006 (-0.003 to +0.016), 0; slope 0.83 | +0.06 (-0.00 to +0.12), 0 | **+0.12 (+0.03 to +0.21), worse** |
| C5 Neural network | **+0.031 (+0.009 to +0.053), worse**; slope 0.53 | **+0.30 (+0.17 to +0.43), worse** | **+0.68 (+0.41 to +0.94), worse** |
| C6 Kalman filter | +0.002 (-0.008 to +0.011), 2 | +0.04 (-0.04 to +0.12), 1 | +0.08 (-0.03 to +0.19), 0 |
| C7 Club home edges | +0.001 (-0.007 to +0.007), 2; slope 1.36 | -0.02 (-0.08 to +0.04), 3 | **-0.054 (-0.096 to -0.014), 4 seasons, 90.9% inside: passes** |

B1 averages on these games: winner 0.618, handicap 6.56, total 9.28 [V].

### NBL: 2023/24 to 2025/26, 450 games [V]

| Challenger | Winner | Handicap | Total |
|---|---|---|---|
| C1 Regression (GLM) | +0.008 (-0.009 to +0.024), 1 | +0.03 (-0.08 to +0.13), 1 | -0.11 (-0.36 to +0.14), 3 |
| C2 Random forest | +0.011 (-0.010 to +0.029), 1; slope 1.55 | +0.18 (-0.01 to +0.35), 1 | -0.03 (-0.38 to +0.33), 1 |
| C3 XGBoost | +0.015 (-0.008 to +0.038), 1 | +0.12 (-0.08 to +0.31), 0 | +0.02 (-0.29 to +0.35), 1 |
| C4 Histogram boosting | **+0.038 (+0.009 to +0.066), worse**; slope 0.51 | **+0.27 (+0.03 to +0.49), worse** | +0.15 (-0.26 to +0.58), 1 |
| C5 Neural network | **+0.078 (+0.028 to +0.132), worse**; slope 0.32 | **+0.54 (+0.08 to +1.00), worse** | +0.67 (-0.12 to +1.40), 1 |
| C6 Kalman filter | -0.002 (-0.014 to +0.011), 2; slope 0.78 | -0.06 (-0.23 to +0.11), 2 | -0.16 (-0.39 to +0.04), 3 |
| C7 Club home edges | +0.013 (-0.002 to +0.029), 0 | **+0.18 (+0.04 to +0.33), worse** | +0.00 (-0.04 to +0.04), 1 |

B1 averages on these games: winner 0.653, handicap 8.55, total 10.71 [V]. The Kalman filter
(C6) comes closest, but every range includes zero, so nothing passes.

No leakage alarm: the highest winner pick rate was 65.2% (EuroLeague) and 62.0% (NBL) [V].

## 4. The NBL width idea (reported, not judged yet)

Widths re-measured every day from the last 365 days of the model's own errors [V]:

| League, market | Test seasons: inside 90% range, fixed to rolling | 2026/27 so far |
|---|---|---|
| NBL handicap | 84.9% to 89.1% (CRPS 8.547 to 8.552) | 41 games: 90.2% to 97.6% |
| NBL total | 86.7% to 90.0% (CRPS 10.708 to 10.672) | 41 games: 85.4% to 90.2% |
| EuroLeague handicap | 90.3% to 89.6% (CRPS 6.562 to 6.564) | 70 games: 97.1% to 97.1% |
| EuroLeague total | 90.9% to 91.0% (CRPS 9.284 to 9.289) | 70 games: 88.6% to 91.4% |

The rolling width brings the NBL ranges back near 90% at almost the same CRPS, but these test
seasons gave the idea, so they cannot judge it. The rule stands: it is judged on 2026/27 NBL
games once 100 have been played [E: about mid December 2026].

## 5. What comes next (each needs Lang's approval)

1. **B3 (choosing a model per league) is now simple**: EuroLeague winner and handicap from Elo,
   total from C7 if it holds up on the 2026/27 games; NBL winner from Elo. A model-per-league
   machine is not needed.
2. **Watch C7 and the width idea on 2026/27 games** as they are played, then B4 (live run and
   Model Lab) for the markets that hold.
3. **The NBA** still waits for B0-D2 (its lock rule).

## 6. Limits

- The B1 test seasons were reused, with a stricter bar (99% and most seasons) to make up for it.
- Only open data: dates, scores and club locations; no injuries, line-ups or odds.
- Several settings sit at the edge of their grids (the simplest end) [V]; the grids were fixed
  beforehand.
