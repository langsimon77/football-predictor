# Latest predictions

Updated Mon 02 Nov 2026, 08:51 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Mon 02 Nov 22:00 | Deportivo v Osasuna | 45% (35% to 54%) | 28% | 27% | Low, Low | 46% | 54% | 1.4 to 1.1 | 5.0 to 4.4 | 4.6 | manager_change, shape_v1, unanswered_question |
| Mon 02 Nov 22:00 | Newcastle v Everton | 45% (38% to 52%) | 26% | 29% | Medium, Low | 54% | 60% | 1.6 to 1.2 | 5.3 to 4.7 | 3.9 | shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 74 | 0.190 | 57% |
| `dc_bayes_v1_noshape` | 64 | 0.195 | 56% |
| `dc_mle_v0` | 74 | 0.195 | 59% |
| `elo_v0` | 74 | 0.187 | 58% |
| `multinomial_v1` | 74 | 0.194 | 58% |
| `ordered_logit_v1` | 74 | 0.195 | 58% |
| `random_forest_v1` | 74 | 0.189 | 58% |
| `stack_v1` | 74 | 0.192 | 58% |
| `xgboost_v1` | 74 | 0.192 | 58% |

Results so far: football_data_co_uk 56, football_data_org 18. 18 still wait for football-data.co.uk, so their corners and cards are scored only if Lang entered them.
