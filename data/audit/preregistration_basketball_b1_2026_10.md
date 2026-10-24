# Plan and pre-registration: basketball phase B1 (EuroLeague and NBL baseline)

Written 24 Oct 2026, before any basketball model was fitted or any forecast made. Lang approved
phase B0 and its proposals B0-D1, B0-D3, B0-D4 and B0-D5, then typed "approved" for B1.
These rules decide what I report and propose afterwards. They cannot change once a test-season
result has been computed; one amendment is allowed before that, recorded here with its reason.

Claim labels: **[V]** Verified, with source. **[E]** Estimate, with basis. **[A]** Assumption.

## In plain words

B1 builds two simple models for the EuroLeague and the NBL and tests them on four (EuroLeague)
and three (NBL) past seasons they never saw. Nothing goes live, nothing is published, no ledger
is written. The result is a report that says, market by market, whether each league is ready
for the next phases.

## 1. Data (step 1)

- Source: the English Wikipedia season articles found in B0 (CC BY-SA 4.0), read with the
  project's polite downloader [V: reports/basketball_data_audit_2026_10.md, section 3].
- One table per league: date, tip-off time in UTC, home club, away club, final scores,
  quarter scores, source article. Regular seasons only (playoffs later, if useful).
- Club IDs come from the Wikipedia link target, which stays the same when a sponsor renames a
  club (for example the link "Hapoel Tel Aviv B.C." shown as "Hapoel IBI Tel Aviv") [V: B0
  samples], plus a tested alias table. A test fails on any name it cannot map.
- EuroLeague times are CET or CEST [V: each article says so]. The NBL time zone is checked in
  this step; it matters only for live locks later.
- Cross-check: EuroLeague game boxes against the season's results grid; a game the two
  disagree on is left out of training and scoring (the Europe pipeline's rule). The two
  differing 2025/26 games from B0 are checked by hand and listed in the report.
- What is scored: the final score including overtime [A: Galsport's basketball markets include
  overtime, as the bet log's two-way winner market suggests; Lang to confirm]. The same tests
  are also reported on regulation time (the sum of the four quarters), not judged.

## 2. Models

**Elo (the benchmark).** Each club has one rating. After a game the winner takes rating points
from the loser, more for an upset and, optionally, for a wide margin. Chance of a home win:
1 / (1 + 10^(-(R_home + H - R_away) / 400)), where H is the home edge. At each new season a
club keeps a share of its rating (the carry-over) and the rest returns to the league average.
For the handicap, the expected margin is b x (R_home + H - R_away), with one scale b fitted on
the tuning seasons, and a bell curve around it whose width is the tuning seasons' error.

**Points model (the candidate).** Each club has an attack and a defence rating:
- home points: league average + home edge + home attack - away defence;
- away points: league average + away attack - home defence.
The ratings are fitted on all earlier games by weighted least squares: a game one half-life
ago counts half as much as today's, and a penalty pulls every rating toward zero so a few games
cannot swing it. Around the expected scores, home and away points follow bell curves with
widths and a correlation measured on the tuning seasons. From these:
- winner: chance the margin (home minus away) is above zero;
- handicap: chance the margin beats the line (for example home -5.5: margin above 5.5);
- total points: chance the total beats the line.
One model gives all three markets Lang chose (team markets first).

**Naive benchmarks.** Winner: the league's home-win rate on the tuning seasons. Margin: a bell
curve around the tuning seasons' average home margin. Total: a bell curve around the league's
average total over the previous 60 days, with the tuning seasons' width.

## 3. Walk-forward rule (no peeking)

Each game day is forecast from games played on earlier days only. Models are refitted before
every game day. No result from a game day is used for any game on that day.

## 4. Seasons

| League | Warm-up only | Tuning | Test |
|---|---|---|---|
| EuroLeague | 2016/17 | 2017/18 to 2021/22 (1,316 games [V]) | 2022/23 to 2025/26 (1,298 games [V]) |
| NBL | 2016/17 | 2017/18 and 2022/23 (261 games [V]) | 2023/24 to 2025/26 (451 games [V]) |

Game counts are played regular-season games from data/basketball/audit_sample.json, before
the cross-check removes any. The NBL has no Wikipedia game lists for 2018/19 to 2021/22, so
its ratings carry across that gap through the half-life.

## 5. Settings, chosen on the tuning seasons only (grids fixed here)

| Model | Setting | Grid | Chosen by |
|---|---|---|---|
| Elo | K (update size) | 10, 15, 20, 25, 30 | winner log loss |
| Elo | home edge H (Elo points) | 50, 75, 100, 125 | same |
| Elo | season carry-over | 0.5, 0.75, 1.0 | same |
| Elo | margin multiplier | on, off | same |
| Points | half-life (days) | 30, 60, 120, 240, 480 | margin CRPS + total CRPS |
| Points | penalty strength | 0.3, 1, 3, 10, 30 | same |

Each league gets its own settings. CRPS (continuous ranked probability score) scores a whole
bell-curve forecast against the real number: lower is better, and it rewards being close and
being honest about the spread.

## 6. Checks, per league, on the test seasons

95% paired bootstrap intervals, 4,000 resamples, game days as the unit, seed 2026.

| Check | Rule |
|---|---|
| W1 | Winner: log loss of the chosen winner model minus the home-win rate: upper end below 0. |
| W2 | Which winner model: the points model if its log loss minus Elo's has an upper end below 0; otherwise Elo (the simpler one). |
| H1 | Handicap: margin CRPS of the chosen margin model minus the naive margin: upper end below 0. |
| H2 | Which margin model: the points model if its margin CRPS minus Elo's has an upper end below 0; otherwise Elo. |
| T1 | Total points: total CRPS of the points model minus the naive total: upper end below 0. |
| K1 | Winner calibration slope of the chosen model between 0.8 and 1.2. |
| K2 | Share of test games inside the chosen model's 90% range: 86% to 94%, for the margin and for the total separately. |
| L | Leakage alarm: winner accuracy of any model above 78% stops the run for a check [E: strong NBA models pick about 68% to 70%]. |

**Decision rule.** In each league, a market goes forward to the next phases only if its benchmark
check passes (W1 winner, H1 handicap, T1 totals) and its calibration check passes (K1 winner,
K2 handicap and totals). No result can change these rules.

Reported, not judged: accuracy, mean error of margin and total, results by season, the chosen
settings, the regulation-time version, and the tuning-season scores.

## Amendment 1 (24 Oct 2026, after Lang approved building, before any model was fitted)

The naive total uses "the previous 60 days", but at the start of each season those days hold
no games (the summer break). Rule added: if the previous 60 days hold fewer than 20 games, the
naive total is the average of the league's last 100 games instead. Nothing else changes.

## 7. Deliverables and limits

- Code in `basketball/` (data, Elo, points model, backtest), tests in `tests/`, report in
  `reports/basketball_b1_backtest_2026_10.md`, all on branch `basketball-b1`; I ask before
  merging or pushing.
- Not in B1: the NBA (waits for B0-D2, the lock rule), odds or market benchmarks (none free;
  B0-D3), tree models and other challengers (B2), a live run, a ledger, the Model Lab (B4).
- The run is small (about 4,000 games, closed-form fits) and runs on Lang's Mac [E].
