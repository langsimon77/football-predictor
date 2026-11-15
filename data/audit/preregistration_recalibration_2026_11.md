# Pre-registration: recalibrating the yes/no football markets (15 November 2026)

Written and committed before the test is run. The test runs once.

## Why

The baseline accuracy table of the November 2026 review
(`reports/accuracy_baseline_2026_11.md`) shows calibration slopes outside 0.8 to 1.2 for
some yes/no markets on the test seasons: Premier League over 2.5 goals (0.61), both teams
score (0.34), over 9.5 corners (0.53) and over 4.5 yellow cards (0.63) look too bold;
Serie A (1.57) and La Liga (1.28) yellow cards look too cautious.

## An honest limit [V]

The idea came from looking at the same seasons the test uses. That is a selection effect:
a pass here is weaker evidence than a pass on seasons nobody had looked at. If a market
passes, the next step is a background trial on new matches, not a switch.

## Hypothesis

A logistic recalibration, fitted only on earlier seasons, lowers the log loss of the
published yes/no forecasts.

## Data

The stored walk-forward forecasts of the published model, seasons 2021/22 to 2025/26
(`data/backtests/` and `data/backtests/trial/`), with the results in
`data/processed/`. No new data. Markets:

- Premier League and La Liga: over 2.5 goals, both teams score, over 9.5 corners,
  over 4.5 yellow cards.
- Serie A and Ligue 1: over 4.5 yellow cards (the only yes/no market shown there).

## Method

For each test season (2023/24, 2024/25, 2025/26), each league and each market:

1. Fit `chance of yes = logistic(a + b * log-odds of the forecast)` on that league's
   forecasts and results from all earlier stored seasons (2021/22 up to the season before).
2. Apply the curve to the test season's forecasts.

Nothing from the test season or later is used. One curve per league and market. No other
method is tried (no isotonic curve, no pooling of leagues, no other lines).

## Metric and pass rule

Change in mean log loss, recalibrated minus published, with a paired bootstrap 95%
interval (2,000 resamples of matches, seed 0).

A market passes when both hold:

1. Pooled over the leagues that show it, the whole interval is below 0.
2. No single league is clearly worse (no league's interval lies wholly above 0).

Reported but not part of the rule: the calibration slope before and after.

## What happens next

- Fail: the published forecasts stay as they are. The result is recorded.
- Pass: the market is listed for Lang's decision. No live model changes without his yes.

Script: `scripts/recalibration_test.py`. Result files:
`reports/recalibration_test_2026_11.md`, `data/audit/recalibration_test_2026_11.json`.
