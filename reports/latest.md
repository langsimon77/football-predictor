# Latest predictions

Updated Thu 26 Nov 2026, 10:55 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Fri 27 Nov 22:00 | Levante v Racing | 56% (46% to 67%) | 22% | 22% | Low, Low | 71% | 71% | 2.2 to 1.4 | 5.8 to 4.7 | 4.2 | manager_change, shape_v1, unanswered_question |
| Fri 27 Nov 22:00 | Forest v Chelsea | 39% (32% to 45%) | 27% | 35% | Low, Medium | 55% | 62% | 1.5 to 1.4 | 4.8 to 5.4 | 4.3 | shape_v1, unanswered_question, referee_unknown |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 116 | 0.195 | 53% |
| `dc_bayes_v1_noshape` | 106 | 0.198 | 53% |
| `dc_mle_v0` | 116 | 0.197 | 55% |
| `elo_v0` | 116 | 0.194 | 55% |
| `multinomial_v1` | 116 | 0.196 | 55% |
| `ordered_logit_v1` | 116 | 0.196 | 54% |
| `random_forest_v1` | 116 | 0.194 | 55% |
| `stack_v1` | 116 | 0.195 | 55% |
| `xgboost_v1` | 116 | 0.195 | 55% |

Results so far: football_data_co_uk 116.
