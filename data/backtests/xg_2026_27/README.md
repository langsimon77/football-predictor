# xG test, part A results

Part A is the walk-forward on matches already played when the xG test was pre-registered
(`data/audit/preregistration_xg_2026_11.md`, section 3). Three GitHub runs of `backtest.yml`
made it. Each arm is refitted weekly, and each match uses the latest fit at or before its own
lock time.

| Arm | Stage name | Run ID |
| --- | --- | --- |
| control (no xG) | `xg_none` | 45200379711 |
| joint | `xg_joint` | 45200387862 |
| blend | `xg_blend` | 45200398219 |

Settings, the same for all three: season key `2026` (the 2026/27 season), leagues EPL, LaLiga,
SerieA and Ligue1, variant `sot` (shots on target), sampler `numpyro`.

## Where part A ends

Part B starts at `2026-11-23T15:00:11Z`. That is the merge time of PR #38 (commit 9bb531e), when
the daily shadows switched on. A match locked before this time is part A. A match locked at or
after it is part B. Each match is counted once.

## Files

- `part_a.parquet`: one row per arm and match.
- `part_a_fits.parquet`: every fit attempt of every arm, with an `arm` column. It holds the
  diagnostics (`rhat_max`, `ess_bulk_min`, `divergences`, `ok`) and, for the joint arm, the
  fitted `xg_mu_x`, `xg_home_x`, `xg_c_att` and `xg_c_def`.
- Built by `scripts/collect_part_a.py` from the downloaded run artifacts.

## Columns of `part_a.parquet`

| Column | Meaning |
| --- | --- |
| `match_id` | match key |
| `league` | league code |
| `lock_utc` | time the forecast was locked |
| `arm` | `control`, `joint` or `blend` |
| `p_home`, `p_draw`, `p_away` | home, draw, away probabilities |
| `p_over_2_5` | probability of more than 2.5 goals |
| `p_btts` | probability both teams score |
| `fit_ok` | true if the latest fit attempt at or before `lock_utc` passed its gate |

`fit_ok` is recorded truthfully here. If a fit failed, the backtest carried the last good fit
forward, but the arm "locks nothing that run" (pre-registration section 6). Pairing and dropping
such matches happens later, in the scoring step, not in this file.

## Leakage note

`result_available_utc` is kickoff plus 3 hours. But football-data.co.uk publishes xG some days
later. So part A sees xG slightly earlier than live running would. Weekly refits keep this
small. It is the same rule shots on target already use.

## Coverage and re-run

The first runs (45200379711, 45200387862, 45200398219) used data up to 8 Nov 2026: 419 matches
per version, locks from 14 Aug to 7 Nov 2026. Matches locked after that and before the part B
start (mainly the 21 to 23 Nov weekend) are not yet in part A.

Rule: part A is re-run once, after football-data.co.uk has published results and xG for every
match locked before 2026-11-23T15:00:11Z (expected by 1 Dec 2026), with the same settings. That
re-run replaces `part_a.parquet` and `part_a_fits.parquet`, and its run IDs are added here.
Nothing is chosen from the first runs' numbers.
