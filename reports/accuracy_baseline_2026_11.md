# Baseline accuracy of every live market (review of November 2026)

Every number is from matches the model had not seen when it made the forecast (walk-forward). Nothing was fitted for this report: it scores the stored test forecasts. [V] verified by `scripts/accuracy_baseline.py`.

How to read it: lower log loss, Brier and RPS are better. The calibration slope says whether a 70% forecast happens 70% of the time: 1 is honest, above 1 the model is too cautious, below 1 too bold. Outside 0.8 to 1.2 is flagged.

## Football

Premier League, La Liga, Serie A and Ligue 1: test seasons 2023/24 to 2025/26, the published model (Bayesian Dixon-Coles with the goals fix). Champions League: 2021/22 to 2025/26, from `data/audit/ucl_backtest_2026_10.json`.

| Competition | Market | Matches | Log loss (95% interval) | Brier | RPS | Slope | Calibration |
|---|---|---|---|---|---|---|---|
| Premier League | home, draw, away | 1,140 | 0.976 (0.948 to 1.004) | 0.581 | 0.199 | 1.00 (0.89 to 1.15) | ok |
| Premier League | over 2.5 goals | 1,140 | 0.675 (0.663 to 0.688) | 0.241 |  | 0.61 (0.25 to 1.01) | **too bold** (weak evidence) |
| Premier League | both teams score | 1,140 | 0.682 (0.671 to 0.694) | 0.245 |  | 0.34 (-0.07 to 0.79) | **too bold** |
| Premier League | over 9.5 corners | 1,140 | 0.676 (0.664 to 0.687) | 0.241 |  | 0.53 (-0.04 to 1.14) | **too bold** (weak evidence) |
| Premier League | over 4.5 yellow cards | 1,140 | 0.663 (0.644 to 0.682) | 0.235 |  | 0.63 (0.29 to 0.97) | **too bold** (weak evidence) |
| La Liga | home, draw, away | 1,140 | 0.969 (0.943 to 0.994) | 0.575 | 0.193 | 1.13 (0.97 to 1.27) | ok |
| La Liga | over 2.5 goals | 1,140 | 0.671 (0.658 to 0.684) | 0.239 |  | 0.93 (0.66 to 1.20) | ok |
| La Liga | both teams score | 1,140 | 0.685 (0.677 to 0.694) | 0.246 |  | 0.92 (0.57 to 1.33) | ok |
| La Liga | over 9.5 corners | 1,140 | 0.682 (0.674 to 0.689) | 0.244 |  | 1.16 (0.66 to 1.68) | ok |
| La Liga | over 4.5 yellow cards | 1,140 | 0.669 (0.659 to 0.679) | 0.238 |  | 1.28 (0.94 to 1.64) | **too cautious** (weak evidence) |
| Serie A | home, draw, away | 1,140 | 0.981 (0.957 to 1.004) | 0.586 | 0.193 | 1.07 (0.92 to 1.21) | ok |
| Serie A | over 4.5 yellow cards | 1,140 | 0.624 (0.611 to 0.637) | 0.217 |  | 1.57 (1.22 to 1.93) | **too cautious** |
| Ligue 1 | home, draw, away | 917 | 1.001 (0.972 to 1.029) | 0.598 | 0.209 | 1.00 (0.84 to 1.17) | ok |
| Ligue 1 | over 4.5 yellow cards | 917 | 0.624 (0.601 to 0.648) | 0.217 |  | 1.12 (0.70 to 1.66) | ok |
| Champions League | home, draw, away | 753 | 0.903 | 0.530 | 0.190 | 1.22 | **too cautious** |

Champions League gain over base rates, RPS: -0.045 (95% interval -0.055 to -0.035; below 0 is better).

## Basketball

Test seasons as in each league's report. Winner: log loss of the Elo model and its gain over a naive forecast. Margin and total: CRPS in points, and how often the 90% range held the result (target 0.90, pass from 0.87 to 0.93).

| League | Games | Winner log loss | Gain over naive (95% interval) | Slope | Calibration | Margin CRPS | Total CRPS | 90% range held: margin, total | Shown on the page |
|---|---|---|---|---|---|---|---|---|---|
| EuroLeague | 1,293 | 0.618 | -0.040 (-0.054 to -0.026) | 0.98 | ok | 6.56 | 9.28 | 0.90, 0.91 | winner, handicap, total points |
| NBL | 450 | 0.653 | -0.036 (-0.061 to -0.010) | 0.95 | ok | 8.55 | 10.71 | 0.85, 0.87 | winner |
| ACB | 612 | 0.582 | -0.095 (-0.130 to -0.058) | 0.96 | ok | 6.79 | 9.65 | 0.88, 0.89 | winner, handicap |
| LBA | 448 | 0.601 | -0.083 (-0.110 to -0.054) | 1.27 | **too cautious** | 6.67 | 10.00 | 0.94, 0.88 | handicap, total points |
| ABA | 466 | 0.484 | -0.188 (-0.223 to -0.151) | 1.44 | **too cautious** | 6.62 | 9.65 | 0.93, 0.90 | handicap, total points |

## Flagged markets

- Premier League over 2.5 goals (0.61): too bold (weak evidence)
- Premier League both teams score (0.34): too bold
- Premier League over 9.5 corners (0.53): too bold (weak evidence)
- Premier League over 4.5 yellow cards (0.63): too bold (weak evidence)
- La Liga over 4.5 yellow cards (1.28): too cautious (weak evidence)
- Serie A over 4.5 yellow cards (1.57): too cautious
- Champions League home, draw, away (1.22): too cautious
- LBA basketball winner (1.27): too cautious
- ABA basketball winner (1.44): too cautious

A flagged basketball winner market is not shown on the page (the league's handicap and total are). A flagged football market keeps its forecast, and the page says on that section which way it leans.
