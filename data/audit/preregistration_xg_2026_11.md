# Pre-registration: expected goals (xG) in the goals model

Written 23 Nov 2026, 05:30 UTC, before any xG forecast was made or scored. Nothing in this file
has been built yet. Status: **plan only, waiting for Lang's approval** (spec S0).

Labels: [V] verified (how), [E] estimate, [A] assumption.

## In plain words (for Lang)

- **The question:** does the goals model forecast better when it also learns from expected goals
  (xG)? xG measures the quality of the chances a team created, which is steadier than the goals
  it happened to score.
- **The data:** only football-data.co.uk's `HxG` and `AxG` columns. They exist for this season
  only. Understat is barred (`docs/DECISIONS.md`, 23 Sep 2026), so there is no older xG.
- **The test:** two xG versions of the current model run as hidden "shadow" models in the daily
  job. They are scored on every league match from the start of 2026/27 to the end of the season,
  side by side with the current model. Nothing you see changes.
- **The verdict comes once, at the end of the season,** by a rule written down today.
- **Honest expectation:** the test will probably end "not shown", even if xG helps a little.
  Adding shots on target improved the result forecast by only 0.0010 log loss [V
  `reports/backtest_phase2_test.md`]. One season can only reveal a gain of about 0.003 to 0.007
  [E, section 7]. The cost is small: about 10 seconds of extra fitting per league per run [E].

## 1. Arms

All three arms are the published model `dc_bayes_v1` (Bayesian Dixon-Coles, shots-on-target
layer, decay 0.002 per day, window 1,100 days, NumPyro, the same priors and seed), changed only as
stated.

| Arm | Name in the ledger | What changes |
|---|---|---|
| Control | `dc_bayes_v1_noshape` (live) / `bdc` (backtest) | Nothing. |
| X1 joint | `dc_bayes_xg_joint_v1` | Adds an xG layer, like the shots-on-target layer. For each match with both xG values, home xG has log mean `mu_x + home_x + c_att * att[home] + c_def * def[away]` (away the same, without `home_x`). It enters as a Poisson-kernel quasi-likelihood `xg * eta - exp(eta)`, weighted by the time decay. Priors: `mu_x ~ N(0.3, 0.5)`, `home_x ~ N(0.1, 0.2)`, `c_att ~ N(1, 0.5)`, `c_def ~ N(1, 0.5)`. |
| X2 blend | `dc_bayes_xg_blend_v1` | For each match with both xG values, the goals term uses the blended count `0.5 * goals + 0.5 * xG` for each side, in the same Poisson kernel. The Dixon-Coles low-score correction still uses the real score. Matches without xG are unchanged. |

Fixed settings, not tuned: the blend weight 0.5 and the xG kernel weight 1 [A]. They are chosen
by reasoning, not by data, so nothing is fitted on the test matches.

Both versions come straight from spec S5.1 ("joint model ... or an xG-blended target. Test
both"). The xG layer leaves every match without xG (all seasons before 2026/27) exactly as
today.

## 2. Data

- `home_xg`, `away_xg` from football-data.co.uk, read by `src/fp/ingest/matches.py` [V].
- Coverage: every 2026/27 match in the four leagues so far, and none before [V, local data to
  8 Nov 2026: Premier League 100 of 100, La Liga 119 of 119, Serie A 110 of 110, Ligue 1 90 of
  90; earlier seasons 0].
- Known unknowns: the xG provider and whether it includes penalties [A,
  `docs/DATA_SOURCES.md`]. The spec asks for non-penalty xG; that can't be done without penalty
  data, so the published values are used as they are.
- No leakage: a match's xG counts only from the time its result row became available
  (`result_available_utc`), through the existing as-of filter (`fp.validate.leakage`).

## 3. Matches scored

All 2026/27 league matches in the Premier League, La Liga, Serie A and Ligue 1 with a 90-minute
result, from the first matchday to the last.

- **Part A, already played:** walk-forward on GitHub (`backtest.yml`). All three arms are refitted
  weekly at a lock time, and each match uses the latest fit at or before its own lock, exactly
  as in `reports/backtest_phase2_test.md`. No team news, no shape fix.
- **Part B, from the day the shadows switch on:** the daily job locks both xG arms with the
  control row (same lock time, same team-news scaling, no shape fix) until the season ends.
- **Pooled:** parts A and B are pooled for the verdict. Nothing is chosen on part A, so pooling
  adds no bias.
- **End date:** the last 2026/27 league match of the four leagues, plus 7 days for results to
  arrive (about 7 Jun 2027 [A]). It is fixed now and not moved.

## 4. Primary rule (the only rule that decides)

- **Measure:** the change in home, draw, away log loss, xG arm minus control, per match.
- **Interval:** a paired bootstrap over matches, 10,000 resamples, seed 2026.
- **Pass:** an arm passes only if its whole **97.5% interval** (two arms, Bonferroni) is below
  zero.
- **Guard:** an arm that passes is still rejected if its over/under 2.5 goals log loss is clearly
  worse (whole 97.5% interval above zero).
- **Both pass:** the one with the lower mean change is proposed.

## 5. Reported, never deciding

- Over/under 2.5 goals log loss, both-teams-to-score log loss, RPS, calibration slope.
- Results per league.
- Part A and part B separately.
- The fitted `c_att` and `c_def` (how much xG agrees with goals about team strength).

## 6. Fits and failures

- Every fit must pass the usual gate: R-hat below 1.01, bulk ESS above 400, no divergences.
- If an xG arm fails its gate in a run, it locks nothing that run. Matches that miss either arm
  are dropped from both (paired), and the report counts them.
- Failures never touch the published forecast (shadows already work this way in
  `src/fp/pipeline/daily.py`).

## 7. How big a gain the test can see [E]

- Two close goals models differ match by match with a standard deviation of 0.085 in log loss.
  That was measured on 3,800 walk-forward matches from 2021 to 2025, `dc_bayes_v1` against the
  fast Dixon-Coles [V, computed 23 Nov 2026 from `data/backtests/`].
- Expected sample: about 450 matches in part A plus about 940 in part B, so about 1,390 in total
  [E, from the fixture counts].
- At 1,390 matches, a gain is found 80% of the time only if it is at least 0.007 log loss (with
  0.085) or 0.0035 (if the xG arm stays closer to the control, at 0.04 [A]).
- For scale: shots on target gave 0.0010 [V]. The market is 0.019 ahead of the model [V, same
  report].

So a pass would be strong evidence. A fail mainly says "not shown in one season", not "xG is
useless".

## 8. What happens after the verdict

- **Pass:** a proposal to Lang to switch the published model, with a new `docs/MODEL_CHANGELOG.md`
  row. The shape fix would then be refitted for the new model before it goes live. Nothing
  changes without Lang's yes.
- **No pass:** the report goes to Lang. The arms stop at the end date, unless Lang asks to run
  2027/28 as a second, separately pre-registered season.
- **Before the end:** a monthly progress line (matches scored, mean change) in the monthly review.
  It carries no verdict, and nothing is changed because of it.

## 9. Build steps after approval (each on a branch, merged only by Lang)

1. `src/fp/models/bayes_dc.py`: an `xg_mode` setting (`none`, `joint`, `blend`) in `BayesParams`
   and `build_model`.
   - Tests: with `xg_mode = none`, the model and its log-likelihood are identical to today's.
   - With xG missing everywhere, both xG modes equal today's model.
   - About 2 hours [E].
2. `src/fp/evaluate/backtest_bayes.py`: an `--xg` option. Then run part A on GitHub (about 30 to
   60 minutes of runner time [E]).
3. `src/fp/pipeline/daily.py` and `shadows`: lock the two xG arms as shadow rows, never published.
   `scripts/check_ledger.py` must still pass. About 2 hours [E].
4. At the end date: `reports/xg_test_2026_27.md` with the rule applied exactly as written here.
