# Phase 2 backtest: test stage

Seasons: 2023/24, 2024/25, 2025/26. Walk-forward: the Bayesian
model is refitted weekly at a lock time; each match uses the latest fit at or before its
own lock. Elo, fast Dixon-Coles (`dc`), and base rates are refitted at every lock.
Variants: `bgoals` = goals only; `bsot` = goals plus shots on target (decision D1);
`bdynamic` = random-walk challenger. Lower is better.

## 1X2, both leagues

| model | n | rps | log_loss | brier | top_pick_hit |
|---|---|---|---|---|---|
| base | 2227 | 0.2289 | 1.0702 | 0.6472 | 0.4432 |
| elo | 2227 | 0.1982 | 0.9786 | 0.5829 | 0.5227 |
| dc | 2227 | 0.1974 | 0.9770 | 0.5811 | 0.5294 |
| bsot | 2227 | 0.1970 | 0.9760 | 0.5803 | 0.5308 |
| mkt_sharp | 2227 | 0.1912 | 0.9571 | 0.5680 | 0.5492 |

## Paired differences in RPS with 95% bootstrap intervals (negative = Bayesian better)

| comparison | mean_rps_diff | ci_low | ci_high |
|---|---|---|---|
| bsot minus base | -0.0319 | -0.0366 | -0.0272 |
| bsot minus elo | -0.0012 | -0.0030 | 0.0006 |
| bsot minus dc | -0.0004 | -0.0015 | 0.0007 |
| bsot minus mkt_sharp | 0.0058 | 0.0037 | 0.0079 |

## Over/under 2.5 goals, log loss

| model | log_loss |
|---|---|
| base | 0.6882 |
| dc | 0.6761 |
| bsot | 0.6732 |
| mkt_sharp | 0.6647 |

## Sampler health

| variant | fits | passed | retried | median_seconds | market_inside_80pct |
|---|---|---|---|---|---|
| sot | 209 | 209 | 0 | 7.0195 | 0.6560 |

## Top-pick accuracy (leakage alarm at 60%)

| model | top_pick |
|---|---|
| base | 0.4432 |
| elo | 0.5227 |
| dc | 0.5294 |
| bsot | 0.5308 |
| mkt_sharp | 0.5492 |

## Per league


### EPL

| model | n | rps | log_loss | brier | top_pick_hit |
|---|---|---|---|---|---|
| base | 1118 | 0.2328 | 1.0748 | 0.6509 | 0.4293 |
| elo | 1118 | 0.2022 | 0.9865 | 0.5891 | 0.5233 |
| dc | 1118 | 0.1999 | 0.9794 | 0.5832 | 0.5295 |
| bsot | 1118 | 0.1994 | 0.9781 | 0.5822 | 0.5295 |
| mkt_sharp | 1118 | 0.1941 | 0.9607 | 0.5708 | 0.5465 |


### LaLiga

| model | n | rps | log_loss | brier | top_pick_hit |
|---|---|---|---|---|---|
| base | 1109 | 0.2250 | 1.0656 | 0.6436 | 0.4572 |
| elo | 1109 | 0.1941 | 0.9707 | 0.5767 | 0.5221 |
| dc | 1109 | 0.1948 | 0.9745 | 0.5790 | 0.5293 |
| bsot | 1109 | 0.1945 | 0.9738 | 0.5784 | 0.5320 |
| mkt_sharp | 1109 | 0.1882 | 0.9534 | 0.5653 | 0.5518 |


Best variant by mean RPS on this stage: **bsot**.

## Run details

Scored once. Predictions came from GitHub Actions run 36182318598 (six runners, one per league and season, NumPyro sampler, weekly refits, 209 of 209 fits passed diagnostics with no retries). Elo, fast Dixon-Coles, base rates, and market columns were recomputed locally from the same data.

## Additional analysis

| Question | Result | 95% interval | Reading |
|---|---|---|---|
| Over/under 2.5 log loss, `bsot` minus `dc` | −0.0029 | −0.0062 to +0.0004 | Better on average, not significant |
| Over/under 2.5 log loss, `bsot` minus base | −0.0146 | −0.0219 to −0.0074 | Clearly better |
| EPL 1X2 RPS, `bsot` minus Elo | −0.0030 | −0.0055 to −0.0003 | Better, significant |
| La Liga 1X2 RPS, `bsot` minus Elo | +0.0005 | −0.0020 to +0.0028 | Level |

### Calibration of the home-win probability

Matches split into five equal groups by each model's home-win forecast. Each cell shows mean forecast, then the observed home-win rate. A slope above 1 means the model is too timid: favourites win more often than it says.

| Model | Group 1 | Group 2 | Group 3 | Group 4 | Group 5 | Slope |
|---|---|---|---|---|---|---|
| `bsot` | 0.23 to 0.18 | 0.35 to 0.33 | 0.43 to 0.40 | 0.53 to 0.55 | 0.68 to 0.74 | 1.22 |
| `dc` | 0.22 to 0.18 | 0.35 to 0.34 | 0.43 to 0.43 | 0.53 to 0.52 | 0.68 to 0.75 | 1.20 |
| Elo | 0.19 to 0.18 | 0.33 to 0.35 | 0.44 to 0.43 | 0.56 to 0.52 | 0.73 to 0.74 | 1.00 |
| Sharp market | 0.19 to 0.16 | 0.33 to 0.33 | 0.44 to 0.43 | 0.55 to 0.55 | 0.73 to 0.75 | 1.08 |

Both Dixon-Coles models squeeze probabilities towards the middle. Elo does not, because its probabilities come from a curve fitted directly to outcomes. A calibration map fitted on the tuning seasons (spec S5.6, Phase 4) is the planned fix.

### Interval width check (PRD item 21)

The sharp market's home-win probability fell inside the `bsot` 80% interval for 65.6% of matches. The intervals express uncertainty about the model's parameters only, not about information the model lacks (lineups, injuries) or its own simplifications. So they are narrower than the gap between the model and the market. They should not be read as "80% sure the true probability is in here".
