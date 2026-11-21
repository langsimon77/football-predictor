# Tip products backtest, November 2026

Test seasons 2023/24 to 2025/26, EPL and La Liga, 503 match days.
Forecasts are walk-forward (each made at its lock time on data known then).
Tier cut points come from 2021/22 and 2022/23 only (`data/tiers/thresholds.json`).
Script: `scripts/backtest_tips.py`. Picks: `data/tips/backtest_picks.parquet`.

## Products

| Product | Picks settled | Model promised (mean) | Hit rate (95% range) | Picks with closing odds | Return per 1 unit at Pinnacle close (95% range) |
|---|---|---|---|---|---|
| Today's Top 3 | 1147 | 82.2% | 81.4% (79.1% to 83.6%) | 17 | too few to judge |
| VIP Bankers | 1625 | 79.6% | 80.4% (78.4% to 82.2%) | 94 | +10.7% (-1.9% to +22.1%) |
| VIP Full Card | 4560 | 77.3% | 77.7% (76.4% to 78.9%) | 259 | +7.8% (+1.0% to +14.1%) |
| VIP Correct Score | 1604 | 12.7% | 15.1% (13.4% to 16.9%) | 0 | too few to judge |
| Diamond | 449 | 75.9% | 75.1% (70.9% to 78.8%) | 63 | -6.2% (-22.5% to +9.0%) |
| Free tips (old) | 2280 | 79.1% | 79.1% (77.4% to 80.7%) | 94 | +10.7% (-1.9% to +22.1%) |
| Premium (old, top 5) | 1339 | 81.0% | 81.9% (79.7% to 83.8%) | 47 | +19.2% (+3.0% to +34.2%) |
| VIP Accumulator 3-fold | 240 | 57.0% | 60.4% (54.1% to 66.4%) | 0 | too few to judge |
| VIP Accumulator 4-fold | 191 | 46.2% | 53.9% (46.8% to 60.8%) | 0 | too few to judge |
| Double | 303 | 70.0% | 69.6% (64.2% to 74.5%) | 0 | too few to judge |
| Treble | 240 | 57.0% | 60.4% (54.1% to 66.4%) | 0 | too few to judge |

How to read it:
- "Model promised" is the average model probability of the picks. If the hit rate's
  95% range covers it, the products are honest: they win about as often as they claim.
- "Return per 1 unit" uses Pinnacle closing odds, only for picks that have them
  (1X2 and over/under 2.5 goals; coupons only when every leg has odds). A negative
  number means a bettor following the picks at closing prices lost money. [Verified, this run]
- Coupons assume independent legs. A double needs both legs to win.

## Premium picks by market

| Product | Picks settled | Model promised (mean) | Hit rate (95% range) | Picks with closing odds | Return per 1 unit at Pinnacle close (95% range) |
|---|---|---|---|---|---|
| 1x2 | 60 | 67.0% | 80.0% (68.2% to 88.2%) | 47 | +19.2% (+3.0% to +34.2%) |
| btts | 21 | 58.7% | 52.4% (32.4% to 71.7%) | 0 | too few to judge |
| corners_over_11_5 | 143 | 80.3% | 75.5% (67.9% to 81.8%) | 0 | too few to judge |
| corners_over_8_5 | 115 | 72.3% | 69.6% (60.6% to 77.2%) | 0 | too few to judge |
| over_1_5 | 613 | 83.6% | 87.1% (84.2% to 89.5%) | 0 | too few to judge |
| over_3_5 | 367 | 83.0% | 80.7% (76.3% to 84.4%) | 0 | too few to judge |
| yellows_over_3_5 | 3 | 73.9% | 100.0% (43.8% to 100.0%) | 0 | too few to judge |
| yellows_over_5_5 | 17 | 89.8% | 94.1% (73.0% to 99.0%) | 0 | too few to judge |

## Limits of this test

- No ensemble-disagreement demotion and no data-quality flags, so a few picks
  rated High here would be Medium live. The record shown is therefore slightly kind. [Assumption]
- Goals forecasts are dc_bayes_v1 before the shape_v1 refit; live tiers use refit cut points.
- Closing odds are a benchmark only. We have no free live odds, so live tips show
  fair odds (1 / probability): a bet only has value if the bookmaker pays more.
