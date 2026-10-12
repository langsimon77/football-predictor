# Pre-registration: Serie A and Ligue 1 backtest (step 2)

Written 12 Oct 2026, before any Serie A or Ligue 1 forecast was made. Lang approved step 2 ("go ahead with step 2"). These rules decide what I propose to Lang afterwards; they cannot be changed after the results are seen.

## What runs

- Walk-forward forecasts for 2021/22 to 2025/26, both leagues, with the live code and the live settings. Nothing is tuned on Serie A or Ligue 1 results, with one exception that copies the live procedure: the challengers' settings are chosen by time-ordered cross-validation on 2017/18 to 2020/21.
- Models: `dc_bayes_v1` (shots on target, NumPyro, weekly refits), fast Dixon-Coles, Elo, league base rates, `corners_total_poisson_v1`, `cards_nb_v1` (no referee: neither league publishes one), the four challengers.
- The published goals forecast is `dc_bayes_v1` with `shape_v1`, its four numbers refitted at the first lock of each month on the previous 730 days of the two trial leagues' own stored forecasts (the live rule, with the live leagues pooled the same way).
- Promoted-club priors are estimated on 2017/18 to 2020/21 from the two trial leagues and their second divisions pooled, as the EPL and La Liga are pooled for the live priors.

## Test seasons

2023/24, 2024/25 and 2025/26, as for the EPL and La Liga. 2021/22 and 2022/23 only supply history for `shape_v1`.

## Checks, per league (95% paired bootstrap intervals, 4,000 resamples, matches as the unit)

| Check | Rule | Basis |
|---|---|---|
| G1 | Home, draw, away RPS of the published forecast minus league base rates: upper end below 0. | The bar the live leagues passed. |
| G2 | Same, minus Elo: upper end below +0.002. | [A] "Level with Elo or better". Live leagues: −0.0012 (−0.0030 to +0.0006). |
| G3 | Same, minus the sharp closing market (Pinnacle, then Betfair Exchange), on matches with that market: mean at most +0.010. | [A] Live leagues: +0.0058. |
| G4 | Over 2.5 goals log loss minus the base rate: upper end below 0. | The bar the live leagues passed. |
| G5 | At least 95% of weekly Bayesian fits pass the diagnostics. | Live: 209 of 209. |
| C1 | Corners: log score of the total minus the league average: upper end below 0. | Live: −0.009. |
| K1 | Yellows: log score of the total minus the league average: upper end below 0. | Live: −0.019. |
| L | Leakage alarm: top-pick accuracy of every model below 60%. | Spec S8. |

Reported, not judged: fast Dixon-Coles, the challengers and the stack (live weights), calibration slope, both teams score, over 1.5 and 3.5, the live confidence cut points applied as they are (hit rates by level).

## What follows

- A league that passes G1 to G5 and L is proposed for background running of its goals markets. Corners join if C1 passes, yellows if K1 passes.
- A failed check means no proposal for that market. Any fix would be a new proposal with its own test.
- Background running means forecasts locked and scored daily but not published. Publishing is a later decision for Lang, on that live record.

## Amendment 1, 13 Oct 2026, before any trial result was scored or downloaded

**Why.** Before scoring the trial leagues, I ran the scoring code on the EPL and La Liga as a reference. Judged one league at a time, the two live leagues fail 4 of their 16 checks: the EPL fails G4 (over 2.5 against the base rate, −0.0072, interval −0.0168 to +0.0022), C1 (corners, −0.0053, −0.0126 to +0.0021) and K1 (yellows, −0.0117, −0.0257 to +0.0012); La Liga fails G2 (against Elo, −0.0004, −0.0027 to +0.0020). The live leagues were accepted on both leagues pooled (2,280 test matches), where all their checks pass. A league holds about 1,100 test matches, so its intervals are about 1.4 times wider. Judged one at a time, the rule above rejects models that the live leagues' own evidence accepted.

At this point, the trial runs had produced only the Elo, fast Dixon-Coles and base-rate forecasts on this Mac, and none had been scored. The GitHub runs were still running or not yet downloaded.

**New rule, replacing "Checks, per league".**
1. Checks G1 to G4, C1, K1 and L are applied to Serie A and Ligue 1 pooled (about 2,000 test matches), with the bars in the table above. This is how the EPL and La Liga were judged.
2. G5 applies to each league.
3. A league is left out if it clearly fails a check by itself: its own interval lies wholly on the wrong side of the bar (lower end above 0 for G1, G4, C1 and K1; lower end above +0.002 for G2), or its own mean RPS gap to the sharp close exceeds +0.010 (G3).
4. Per-league results are reported in full.

With the same code, the EPL and La Liga pooled pass every check, and neither league clearly fails any check by itself.
