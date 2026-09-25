# Phase 2 backtest: tune stage

Seasons: 2021/22, 2022/23. Walk-forward: the Bayesian
model is refitted weekly at a lock time; each match uses the latest fit at or before its
own lock. Elo, fast Dixon-Coles (`dc`), and base rates are refitted at every lock.
Variants: `bgoals` = goals only; `bsot` = goals plus shots on target (decision D1);
`bdynamic` = random-walk challenger. Lower is better.

## 1X2, both leagues

| model | n | rps | log_loss | brier | top_pick_hit |
|---|---|---|---|---|---|
| base | 1520 | 0.2291 | 1.0657 | 0.6442 | 0.4566 |
| elo | 1520 | 0.2016 | 0.9873 | 0.5874 | 0.5388 |
| dc | 1520 | 0.2022 | 0.9876 | 0.5884 | 0.5316 |
| bgoals | 1520 | 0.2031 | 0.9903 | 0.5901 | 0.5349 |
| bsot | 1520 | 0.2014 | 0.9846 | 0.5861 | 0.5355 |
| mkt_sharp | 1520 | 0.1951 | 0.9657 | 0.5737 | 0.5461 |

## Paired differences in RPS with 95% bootstrap intervals (negative = Bayesian better)

| comparison | mean_rps_diff | ci_low | ci_high |
|---|---|---|---|
| bgoals minus base | -0.0261 | -0.0311 | -0.0206 |
| bgoals minus elo | 0.0014 | -0.0007 | 0.0035 |
| bgoals minus dc | 0.0009 | -0.0001 | 0.0018 |
| bgoals minus mkt_sharp | 0.0079 | 0.0049 | 0.0110 |
| bsot minus base | -0.0278 | -0.0334 | -0.0217 |
| bsot minus elo | -0.0003 | -0.0023 | 0.0018 |
| bsot minus dc | -0.0008 | -0.0022 | 0.0005 |
| bsot minus mkt_sharp | 0.0062 | 0.0037 | 0.0089 |

## Over/under 2.5 goals, log loss

| model | log_loss |
|---|---|
| base | 0.6914 |
| dc | 0.6836 |
| bgoals | 0.6826 |
| bsot | 0.6797 |
| mkt_sharp | 0.6768 |

## Sampler health

| variant | fits | passed | retried | median_seconds | market_inside_80pct |
|---|---|---|---|---|---|
| goals | 136 | 136 | 9 | 6.5836 | 0.7066 |
| sot | 136 | 136 | 0 | 9.4460 | 0.6493 |

## Top-pick accuracy (leakage alarm at 60%)

| model | top_pick |
|---|---|
| base | 0.4566 |
| elo | 0.5388 |
| dc | 0.5316 |
| bgoals | 0.5349 |
| bsot | 0.5355 |
| mkt_sharp | 0.5461 |

## Per league


### EPL

| model | n | rps | log_loss | brier | top_pick_hit |
|---|---|---|---|---|---|
| base | 760 | 0.2329 | 1.0638 | 0.6434 | 0.4566 |
| elo | 760 | 0.2010 | 0.9728 | 0.5777 | 0.5395 |
| dc | 760 | 0.2018 | 0.9746 | 0.5791 | 0.5382 |
| bgoals | 760 | 0.2025 | 0.9771 | 0.5806 | 0.5382 |
| bsot | 760 | 0.2022 | 0.9756 | 0.5796 | 0.5342 |
| mkt_sharp | 760 | 0.1932 | 0.9490 | 0.5625 | 0.5658 |


### LaLiga

| model | n | rps | log_loss | brier | top_pick_hit |
|---|---|---|---|---|---|
| base | 760 | 0.2254 | 1.0675 | 0.6449 | 0.4566 |
| elo | 760 | 0.2022 | 1.0019 | 0.5971 | 0.5382 |
| dc | 760 | 0.2026 | 1.0006 | 0.5977 | 0.5250 |
| bgoals | 760 | 0.2036 | 1.0035 | 0.5996 | 0.5316 |
| bsot | 760 | 0.2005 | 0.9936 | 0.5927 | 0.5368 |
| mkt_sharp | 760 | 0.1971 | 0.9823 | 0.5849 | 0.5263 |


Best variant by mean RPS on this stage: **bsot**.
