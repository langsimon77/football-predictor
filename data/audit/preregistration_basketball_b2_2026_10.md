# Plan and pre-registration: basketball phase B2 (challengers)

Written 25 Oct 2026, before any B2 model was fitted. Lang approved the B1 results ("Approved: B1
results") and typed "start phase B2". These rules decide what I report and propose afterwards.
They cannot change once a B2 test-season result has been computed; one amendment is allowed
before that, recorded here with its reason.

Claim labels: **[V]** Verified, with source. **[E]** Estimate, with basis. **[A]** Assumption.

## In plain words

B1 kept Elo (winner, handicap) and the points model (total points) and showed they beat naive
guesses: all three EuroLeague markets and the NBL winner passed
[V: reports/basketball_b1_backtest_2026_10.md]. B2 tests whether newer methods from Lang's brief
beat those B1 models on the same games. A method is kept only if it is clearly better, steadily
across seasons, and still honest about its uncertainty. Nothing goes live in B2.

## 1. New data (step 1)

- **Club locations**: each club's home city and its coordinates, from Wikipedia (CC BY-SA),
  in `data/manual/basketball_club_cities.csv`; a test fails if any club has no location.
- **Features**, each computed for a game from earlier days only:
  - F1: Elo difference (the B1 Elo, B1 settings);
  - F2: the B1 points model's expected margin and expected total;
  - F3: days since each team's previous game in our data (in the EuroLeague this misses the
    clubs' domestic games, so it mainly marks double-round weeks [V: our data holds EuroLeague
    games only]);
  - F4: the away team's travel distance (km between the two home cities);
  - F5: each team's recent form: its average margin minus Elo's expected margin over its last
    5 games;
  - F6: how far into the season the game is (games played so far).

## 2. Challengers

| ID | Family (Lang's brief) | Model | Settings grid (tuning seasons only) |
|---|---|---|---|
| C1 | Statistical models (GLMs) | Logistic regression (winner), linear regression (margin, total) on F1 to F6 | penalty 0.01, 0.1, 1, 10 |
| C2 | Tree ensembles | Random forest | depth 3, 5, 8; smallest leaf 20, 50 games |
| C3 | Tree ensembles | XGBoost gradient boosting | depth 2, 3; learning rate 0.03, 0.1; rounds 100, 300 |
| C4 | Tree ensembles | Histogram gradient boosting (scikit-learn, the LightGBM method) | leaves 7, 15; learning rate 0.03, 0.1; rounds 100, 300; penalty 0, 1 |
| C5 | Neural networks | A small network reading each team's last 10 results (margins and totals) plus F1 | hidden units 16, 32; penalty 0.001, 0.01 |
| C6 | Time series (state space) | Kalman-filter ratings: each club's attack and defence drift a little every day and are updated after each game | daily drift 0.02, 0.05, 0.1, 0.2 points squared; extra drift at a new season 5, 20, 50 |
| C7 | Statistical models | The B1 points model plus a home edge for each club (penalised toward the league's) | club home-edge penalty 1, 3, 10, 30 |

Winner forecasts come from each model's chances (C1 to C5) or from its margin bell curve (C6,
C7). Margin and total forecasts are bell curves around each model's expected value, with the
width measured on its tuning-season errors, as in B1.

Not tested in B2, with reasons; Lang may ask for them, which needs new libraries:
- **Prophet and ARIMA** forecast one long series with trends and seasons. A club's season is
  only 30 to 40 games, and a game is a head-to-head result, not one series [E]. C6 is the
  state-space form of the same idea and needs no new library.
- **LSTMs and Transformers** usually need tens of thousands of examples; we have
  2,847 EuroLeague and 814 NBL games [V: B1 data, 2016/17 to 2025/26; the "tens of thousands"
  is E: common practice for sequence networks]. C5 is the small,
  testable version of "learning from the recent sequence". They would also need PyTorch, a
  large download on Lang's connection [A].
- **Choosing a model per league automatically** (the AutoML idea) is phase B3.

## 3. How every challenger is fitted

- Features are built day by day from earlier days only (the B1 rule).
- C1 to C5 are refitted at the start of each season and then every 28 days, on all earlier
  games. C6 and C7 update every game day.
- Settings: time-ordered cross-validation on the tuning seasons only. Each tuning season is
  forecast from the seasons before it, and the setting with the lowest average tuning score is
  chosen per league and per market (winner: log loss; margin and total: CRPS).
- Seasons are B1's: EuroLeague tuning 2017/18 to 2021/22, test 2022/23 to 2025/26; NBL tuning
  2017/18 and 2022/23, test 2023/24 to 2025/26; 2016/17 is warm-up only.

## 4. Checks on the test seasons

Each challenger is compared with the B1 model for that market: Elo for the winner and the
handicap, the points model for the total. Paired bootstrap over game days, 4,000 resamples,
seed 2027.

The B1 test seasons have been seen once already (by the B1 models only). To guard against luck
across many comparisons (7 challengers, 3 markets, 2 leagues), the bar is higher than in B1:

| Check | Rule |
|---|---|
| A1 | Challenger's score minus the B1 model's: upper end of the **99%** interval below 0. |
| A2 | Better than the B1 model in at least 3 of the 4 EuroLeague test seasons, or 2 of the 3 NBL ones. |
| A3 | Calibration as in B1: winner slope 0.8 to 1.2; margin or total: 86% to 94% inside the 90% range. |
| L | Leakage alarm: any winner pick rate above 78% stops the run for a check. |

**Decision rule.** A challenger can replace the B1 model for a market in a league only if it
passes A1, A2 and A3. If several pass, B3 chooses between them. A challenger that passes is
then watched on the 2026/27 games as they are played before it is used live (B4).

## 5. The NBL width idea (from B1)

B1's NBL handicap failed because its bell curve was too narrow on the test seasons (84.9% inside
the 90% range) [V: B1 report]. Variant: the widths are re-measured day by day from the model's
own errors over the previous 365 days (at least 100 games, otherwise the tuning width).

This idea came from the B1 test result, so those seasons cannot judge it fairly. Its
test-season numbers are reported, not judged. It is judged on the 2026/27 NBL games once 100
have been played [E: about mid December 2026]: it passes if 86% to 94% of them fall inside its
90% range and its CRPS is no worse than the fixed width's.

## 6. Deliverables and limits

- Code in `basketball/` (features, challengers, backtest), tests in `tests/`, report in
  `reports/basketball_b2_challengers_2026_10.md`. This shared folder stays on branch
  `basketball-b1` (identical to main when B2 starts); I ask before merging or pushing.
- Tuned settings are committed before the test seasons are scored, as in B1.
- Not in B2: the NBA (waits for B0-D2), odds (none free), a live run, a ledger, the Model Lab.
- The run is larger than B1 but fits on Lang's Mac [E: about 100 refits per tree setting].
