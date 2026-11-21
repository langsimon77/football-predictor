# Tip products backtest, November 2026

Test seasons 2023/24 to 2025/26, EPL and La Liga, 503 match days.
Forecasts are walk-forward (each made at its lock time on data known then).
Tier cut points come from 2021/22 and 2022/23 only (`data/tiers/thresholds.json`).
Script: `scripts/backtest_tips.py`. Picks: `data/tips/backtest_picks.parquet`.

## Products

| Product | Picks settled | Model promised (mean) | Hit rate (95% range) | Picks with closing odds | Return per 1 unit at Pinnacle close (95% range) |
|---|---|---|---|---|---|
| Free tips | 2280 | 73.9% | 73.9% (72.0% to 75.6%) | 341 | +3.5% (-3.3% to +9.8%) |
| Premium | 1274 | 73.8% | 74.5% (72.0% to 76.8%) | 264 | +3.2% (-3.8% to +10.7%) |
| Diamond | 444 | 75.0% | 74.1% (69.8% to 78.0%) | 75 | -5.3% (-19.0% to +8.9%) |
| Double | 293 | 59.2% | 57.7% (52.0% to 63.2%) | 10 | too few to judge |
| Treble | 225 | 44.2% | 44.9% (38.5% to 51.4%) | 1 | too few to judge |

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
| 1x2 | 211 | 72.3% | 82.0% (76.2% to 86.6%) | 178 | +8.4% (+1.1% to +15.7%) |
| btts | 101 | 60.7% | 66.3% (56.7% to 74.8%) | 0 | too few to judge |
| corners_over_10_5 | 1 | 68.0% | 100.0% (20.7% to 100.0%) | 0 | too few to judge |
| corners_over_11_5 | 350 | 80.2% | 77.4% (72.8% to 81.5%) | 0 | too few to judge |
| corners_over_8_5 | 494 | 73.8% | 73.7% (69.6% to 77.4%) | 0 | too few to judge |
| over_2_5 | 96 | 65.6% | 55.2% (45.3% to 64.8%) | 86 | -7.4% (-24.3% to +9.8%) |
| yellows_over_3_5 | 4 | 75.0% | 100.0% (51.0% to 100.0%) | 0 | too few to judge |
| yellows_over_5_5 | 17 | 89.8% | 94.1% (73.0% to 99.0%) | 0 | too few to judge |

## Limits of this test

- No ensemble-disagreement demotion and no data-quality flags, so a few picks
  rated High here would be Medium live. The record shown is therefore slightly kind. [Assumption]
- Goals forecasts are dc_bayes_v1 before the shape_v1 refit; live tiers use refit cut points.
- Closing odds are a benchmark only. We have no free live odds, so live tips show
  fair odds (1 / probability): a bet only has value if the bookmaker pays more.
