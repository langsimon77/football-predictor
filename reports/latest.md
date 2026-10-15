# Latest predictions

Updated Thu 15 Oct 2026, 07:14 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Fri 16 Oct 21:00 | Deportivo v Levante | 45% (35% to 56%) | 26% | 29% | Low, Low | 56% | 61% | 1.6 to 1.3 | 5.2 to 4.8 | 4.2 | shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 19 | 0.170 | 53% |
| `dc_bayes_v1_noshape` | 9 | 0.178 | 44% |
| `dc_mle_v0` | 19 | 0.181 | 53% |
| `elo_v0` | 19 | 0.160 | 53% |
| `multinomial_v1` | 19 | 0.179 | 53% |
| `ordered_logit_v1` | 19 | 0.178 | 53% |
| `random_forest_v1` | 19 | 0.163 | 53% |
| `stack_v1` | 19 | 0.171 | 53% |
| `xgboost_v1` | 19 | 0.166 | 53% |

Results so far: football_data_co_uk 19.
