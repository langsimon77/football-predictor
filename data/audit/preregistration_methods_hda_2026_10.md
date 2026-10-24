# Plan and pre-registration: new model families for home, draw, away (EPL and La Liga)

Written 24 Oct 2026, before any new method was built or scored. Lang asked to apply the
methods from the basketball brief (tree ensembles, deep learning, time series, GLMs, choosing a
model per league) to the Model Lab "to improve predictions accuracy", then chose: "write a
pre-registered test plan for the new methods, starting with EPL and La Liga home, draw, away.
Ask me before building it." These rules decide what I propose afterwards. They cannot change
once a test-season result has been computed; one amendment is allowed before that, recorded
here with its reason.

Claim labels: **[V]** Verified, with source. **[E]** Estimate, with basis. **[A]** Assumption.

## In plain words

Each new method gets the same exam the current challengers passed through: it learns from
older seasons, then forecasts three seasons it never saw (2023/24 to 2025/26), match by match,
using only what was known before each match. It replaces the published forecast only if it is
clearly better, and Lang approves the change. "No change" is a likely and acceptable result
[E: in Phase 4 the best challenger beat the published model by only 0.0022 log loss, inside
noise, while the bookmakers' closing odds were 0.017 better than both;
reports/backtest_phase4.md]. The test tells us where extra effort pays and where it does not.

## 1. What is already known [V: reports/backtest_phase4.md, test seasons]

| Forecast | Log loss |
|---|---|
| Published Bayesian model | 0.9759 |
| Multinomial GLM / ordered logit | 0.9739 / 0.9746 |
| Random forest / XGBoost | 0.9752 / 0.9775 |
| Stack of the challengers | 0.9738 |
| Closing market (benchmark only) | 0.9571 |

GLMs, random forests, XGBoost and a stack are therefore already tested and run every day as
shadow forecasts. This plan adds what is missing.

## 2. Methods tested

All use the Phase 4 feature table (`fp.features.ml_features`: fast Dixon-Coles outputs, Elo
gap, rolling team averages of shots, corners, fouls and yellows, rest days, season context) and
never bookmaker odds (spec S5.5). Settings are chosen by time-ordered cross-validation on
2017/18 to 2020/21, the folds the current challengers use, by multiclass log loss.

| ID | Method | What it adds | Settings grid (fixed here) |
|---|---|---|---|
| N1 | LightGBM | A faster tree ensemble, like XGBoost | leaves 7, 15, 31; trees 150, 400; learning rate 0.03, 0.1 |
| N2 | LSTM | Reads each club's last matches in order (goals for and against, shots, shots on target, corners, home or away, rest days, opponent's Elo then) and joins them with the match features | memory size 16, 32; matches read 5, 10 |
| N3 | Transformer | The same inputs, read by attention instead of a memory cell (2 layers, 2 heads) | width 16, 32; matches read 5, 10 |
| N4 | Time-series form features | For each club, ARIMA forecasts of next-match goals for and against and shots on target for and against, from its own past matches; added as four features to the multinomial GLM and to N1 | ARIMA order by AIC, p and q from 0 to 2, no differencing |
| N5 | Prophet form features | As N4, with Prophet (yearly pattern on, weekly off) instead of ARIMA | Prophet defaults otherwise |
| N6 | Model per league | For each league, the forecast with the lowest log loss on 2021/22 and 2022/23 among: the published model, Elo, fast Dixon-Coles, the four current challengers, the stack, and N1 to N5 | none |
| N7 | New stack | The Phase 4 stack method with N1 to N5 added as members, weights fitted on 2021/22 and 2022/23 | as Phase 4 |

Deep models (N2, N3): dropout 0.2, weight decay 0.0001, early stopping on the latest 10% of
the training matches in time order, and the average of 5 seeds (fixed seeds 1 to 5) so one
lucky start cannot decide. All N1 to N5 refit on the same dates as the current challengers
(the `refit_utc` column of `data/backtests/challengers_walkforward_2021_2025.parquet` [V]).

## 3. Seasons

| Use | Seasons | Matches |
|---|---|---|
| Choosing settings (time-ordered folds) | 2017/18 to 2020/21 | as for the current challengers |
| Fitting the stack and choosing per league (N6, N7) | 2021/22 and 2022/23 | 1,520 [V: baselines file] |
| Test, scored once | 2023/24 to 2025/26 | 2,280 [V: baselines file] |

The published forecast is the stored walk-forward of `dc_bayes_v1` with `shape_v1`
(`p_home`, `p_draw`, `p_away` in `data/backtests/baselines_2021_2025_shape_v1.parquet`, 3,800
matches [V]).

## 4. Checks, on the test seasons

Paired bootstrap over matches (the Phase 4 helper `fp.evaluate.backtest.paired_ci`), 4,000
resamples, seed 2026.

| Check | Rule |
|---|---|
| A1 | A method is proposed to replace the published home, draw, away forecast only if its log loss minus the published forecast's has a **99%** interval entirely below zero, EPL and La Liga pooled. |
| A2 | The same difference in each league separately, 95% intervals: reported. A method that passes A1 but is worse on average in one league is proposed for the other league only, through N6. |
| A3 | N6 (model per league) and N7 (new stack) are judged by the A1 rule like any method. |
| C | Calibration guard for anything proposed: expected calibration error at most 0.005 above the published forecast's, and calibration slope between 0.8 and 1.25. |
| L | Leakage alarm: top-pick accuracy above 60% for any method stops the run for a check (spec S8). |

**Why 99%, not the usual 95% [A].** The project's rule is a 95% interval below zero (DECISIONS,
25 Sep 2026). Seven methods are tested here at once, so one could pass by luck about one time
in six at 95% [E: 1 minus 0.975 to the 7th power is 16%]. The 99% interval keeps that near
one in thirty [E: 1 minus 0.995 to the 7th power is 3.4%]. Lang approves or changes this with
the plan.

Reported, not judged: RPS, Brier, accuracy, results by season and league, the chosen settings,
each method against the current stack and against the markets (matches with odds).

## 5. Running it

- New packages (LightGBM, PyTorch for the CPU, statsmodels, Prophet) go in a separate optional
  group, so the daily run never installs them. Exact versions are pinned when built.
- The backtest runs on GitHub's free runners, one job per method, as the earlier long
  backtests did, so Lang's Mac and connection are not needed [V: runners have 4 CPUs, 16 GB,
  6-hour job limit; DATA_SOURCES.md]. Estimated time: under an hour per method [E: about
  4,000 matches, a few hundred refits, small networks].
- Outputs: walk-forward forecasts in `data/backtests/methods_walkforward_2021_2025.parquet` and
  a report `reports/methods_hda_backtest_2026_10.md`, on a branch; I ask before merging.
- Nothing enters the daily run, the ledger or the Model Lab. A method that passes is only
  proposed, with an entry in `docs/MODEL_CHANGELOG.md`, and waits for Lang's approval.

## Amendment 1 (24 Oct 2026, after Lang approved building, before any method was scored)

Details the plan left open, fixed now; no check, grid, season or threshold changes.

1. **N2 and N3 are written in JAX, not PyTorch.** JAX is already installed (NumPyro uses it),
   so no large new download is needed. Same networks. Training: Adam, learning rate 0.001,
   batches of 256, at most 60 passes over the data, stop after 5 passes without improvement
   on the latest 10% of training matches, keep the best pass.
2. **Network shapes.** LSTM: one layer reads each club's matches, oldest first; the two clubs'
   final states and the match features go through one 32-unit layer to the three outcomes.
   Transformer: each read match is projected to the model width, plus a learned position;
   2 layers, 2 heads, feed-forward width twice the model width; the club vector is the mean
   over its read matches; then the same 32-unit layer.
3. **Sequence inputs per read match:** goals, shots, shots on target and corners, each for
   and against; home or away; rest days before it (at most 14); the opponent's Elo before it
   (the project's Elo, `fp.models.elo`). Scaled with the training matches' means and spreads.
   Only matches whose result was known at the forecast's lock are read.
4. **Form features (N4, N5).** For every club, ARIMA and Prophet are refitted at the first
   lock of every month from 2017/18 on (the challengers' refit rule). Between refits, ARIMA
   updates its forecast with each new result at fixed parameters; Prophet forecasts from that
   month's fit. Each match gets eight columns: the four forecasts (goals for and against,
   shots on target for and against) for each of its two clubs. A club with fewer than 20
   top-flight matches gets no form features (left empty: the GLM fills the median, LightGBM
   handles gaps).
5. **N4 and N5 each give two forecasts** (the multinomial GLM and LightGBM, each with the four
   form features, settings chosen by the same cross-validation). The one with the lower log
   loss on 2021/22 and 2022/23 represents the method in A1, N6 and N7; both are reported.
6. **Stacks.** The current stack is rebuilt as in Phase 4 (Elo, fast Dixon-Coles, the
   Bayesian model without the goals fix, and the four challengers; weights fitted on 2021/22
   and 2022/23). N7 adds the representatives of N1 to N5. When N6 chooses on 2021/22 and
   2022/23, both stacks use cross-fitted forecasts (weights from the other season), Phase 4's
   rule, so no candidate is judged on a season that set its own weights.

## 6. Not in this plan

- Goal lines, corners, cards, Serie A and Ligue 1, the Champions League and the Europa and
  Conference League pipeline: tested later with the same rules, only for methods that pass here
  [E: if a method cannot beat the published model on the two leagues with the most data, it is
  unlikely to on thinner data].
- Bookmaker odds as a model input: forbidden by spec S5.5. Lifting that rule is Lang's
  separate decision.
