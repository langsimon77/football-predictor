# Latest predictions

Updated Thu 29 Oct 2026, 08:29 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Fri 30 Oct 22:00 | Villarreal v Espanyol | 66% (59% to 72%) | 20% | 14% | Low, Low | 59% | 56% | 2.1 to 0.9 | 5.9 to 4.2 | 4.2 | manager_change, shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 56 | 0.180 | 55% |
| `dc_bayes_v1_noshape` | 46 | 0.184 | 54% |
| `dc_mle_v0` | 56 | 0.187 | 57% |
| `elo_v0` | 56 | 0.179 | 54% |
| `multinomial_v1` | 56 | 0.185 | 57% |
| `ordered_logit_v1` | 56 | 0.186 | 55% |
| `random_forest_v1` | 56 | 0.180 | 55% |
| `stack_v1` | 56 | 0.183 | 55% |
| `xgboost_v1` | 56 | 0.183 | 54% |

Results so far: football_data_co_uk 56.
