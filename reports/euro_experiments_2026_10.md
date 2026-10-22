# Europe pipeline: October 2026 checks (tasks 5.3 to 5.8)

Pre-registered in `data/audit/preregistration_euro_2026_10.md` before any result was run.
Numbers: `data/euro/experiments_2026_10.json`, `data/euro/benchmark_2026_10.json`. Code:
`pipeline_euro/experiments.py`, `pipeline_euro/benchmark.py`.

## Reference (reproduced from the public sources)

Log loss of home, draw, away, walk-forward (monthly refits), blended 0.8 goals model and 0.2 Elo:
0.9393 on all 1,199 European matches since July 2023, 0.9480 on the 938 tuning matches,
0.9082 on the 261 test matches since July 2025.

## Results on the 261 test matches (lower is better)

| Task | What was tried | Change | 95% range | Verdict |
|---|---|---|---|---|
| 5.3 | Best setting on the tuning matches: half-life 730 days, penalty 0.0003, rho fitted monthly (it moved from -0.05 to +0.06) | -0.0028 | -0.0087 to +0.0029 | Not shown |
| 5.4 | Over 2.5 goals: goals shift by competition (UCL +0.018, UEL +0.005, UECL -0.024) | -0.0020 | -0.0049 to +0.0008 | Not shown |
| 5.4 | Over 2.5 goals: isotonic calibration | +0.0074 | -0.0084 to +0.0281 | Worse |
| 5.5 | Home, draw, away: temperature 0.85 (sharper) | -0.0034 | -0.0127 to +0.0072 | Not shown |
| 5.5 | Home, draw, away: Dirichlet calibration | +0.0002 | -0.0176 to +0.0195 | No change |
| 5.6 | Stacked blend with each team's recent match count | +0.0088 | -0.0104 to +0.0301 | Worse; walked forward over all 1,199: 0.9437, not below 0.9393 |
| 5.7 | Elo start for new clubs from the goals model's league strength (63 test matches with a thin-data team) | -0.0027 | -0.0055 to -0.0002 | Not shown after the correction for five tries (p 0.023 against 0.010) |

Holm correction across the five pre-registered comparisons: none passes, so nothing is proposed.

What the numbers say:
- The totals are under-forecast: over 2.5 goals was predicted 61.3% and happened 65.5% on
  the test matches (57.1% and 58.5% on the tuning matches). Over 1.5 and over 3.5 lean the
  same way; both teams to score is right (57.2% against 57.5%). The competition shift points
  the right way but is too small to prove on 261 matches.
- The new-club Elo start is the one lead: its uncorrected interval is below zero, and it also
  helps a little on all test matches (-0.0007, -0.0015 to 0.0000). Next step, pre-registered:
  run it beside the current start on the next 300 European matches and adopt only if it still
  wins there.

## Against the bookmakers (5.8)

No free source has odds for the Europa or Conference League. Where odds exist, 13,038
top-division domestic matches from 4 Jul 2023 to 3 Sep 2026 (xgabora's Matches.csv,
football-data.co.uk odds), the same goals model refitted monthly scored 0.9926; the bookmakers
(average odds, 6.0% margin removed) 0.9705. Difference +0.0221 (+0.0193 to +0.0252): the
bookmakers are clearly better, as in every earlier test in this project.

## Corners and cards (5.9)

Not added. No free per-match source with at least two seasons of corners or cards exists for
UEFA competitions (openfootball has scores only; football-data.org's free tier does not cover
the two competitions; Matches.csv covers domestic leagues only). The cards keep the note
"not shown: no free data for these competitions".
