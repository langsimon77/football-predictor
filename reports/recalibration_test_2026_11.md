# Recalibrating the yes/no football markets: test result (November 2026)

Rules: `data/audit/preregistration_recalibration_2026_11.md`, committed before this test ran. One run. [V] verified by `scripts/recalibration_test.py`.

Change in log loss, recalibrated minus published (below 0 is better), test seasons 2023/24 to 2025/26. A market passes when the whole pooled 95% interval is below 0 and no league is clearly worse.

| Market | Matches | Pooled change (95% interval) | By league | Slope before | Slope after | Result |
|---|---|---|---|---|---|---|
| over 2.5 goals | 2,280 | +0.0009 (-0.0007 to +0.0024) | Premier League +0.0004 (-0.0021 to +0.0028); La Liga +0.0013 (-0.0006 to +0.0032) | 0.88 | 0.91 | fail |
| both teams score | 2,280 | -0.0010 (-0.0031 to +0.0010) | Premier League +0.0001 (-0.0032 to +0.0033); La Liga -0.0021 (-0.0047 to +0.0004) | 0.66 | 0.81 | fail |
| over 9.5 corners | 2,280 | +0.0019 (-0.0003 to +0.0041) | Premier League +0.0001 (-0.0017 to +0.0019); La Liga +0.0038 (-0.0001 to +0.0076) | 1.01 | 1.25 | fail |
| over 4.5 yellow cards | 4,337 | -0.0006 (-0.0028 to +0.0016) | Premier League -0.0012 (-0.0064 to +0.0039); La Liga +0.0026 (-0.0006 to +0.0060); Ligue 1 +0.0035 (+0.0010 to +0.0061); Serie A -0.0068 (-0.0118 to -0.0016) | 1.01 | 0.90 | fail |

No live forecast changed. A passing market is a candidate for Lang's decision only.
