# Latest predictions

Updated Mon 26 Oct 2026, 07:19 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Mon 26 Oct 22:00 | Sevilla v Osasuna | 47% (41% to 53%) | 27% | 26% | Low, Low | 46% | 53% | 1.4 to 1.0 | 4.6 to 4.2 | 5.0 | manager_change, shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 46 | 0.172 | 59% |
| `dc_bayes_v1_noshape` | 36 | 0.176 | 58% |
| `dc_mle_v0` | 46 | 0.181 | 59% |
| `elo_v0` | 46 | 0.171 | 57% |
| `multinomial_v1` | 46 | 0.178 | 59% |
| `ordered_logit_v1` | 46 | 0.179 | 57% |
| `random_forest_v1` | 46 | 0.171 | 57% |
| `stack_v1` | 46 | 0.175 | 57% |
| `xgboost_v1` | 46 | 0.173 | 57% |

Results so far: football_data_co_uk 40, football_data_org 6. 6 still wait for football-data.co.uk, so their corners and cards are scored only if Lang entered them.
