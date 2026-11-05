# Latest predictions

Updated Thu 05 Nov 2026, 09:25 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Fri 06 Nov 22:00 | Everton v Coventry | 51% (41% to 60%) | 27% | 22% | Low, Low | 45% | 51% | 1.5 to 1.0 | 4.9 to 4.9 | 3.6 | shape_v1, unanswered_question, referee_unknown |
| Fri 06 Nov 22:00 | Sevilla v Alavés | 44% (38% to 50%) | 28% | 28% | Low, Medium | 44% | 53% | 1.4 to 1.1 | 4.7 to 4.4 | 4.9 | shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 76 | 0.192 | 57% |
| `dc_bayes_v1_noshape` | 66 | 0.197 | 56% |
| `dc_mle_v0` | 76 | 0.197 | 59% |
| `elo_v0` | 76 | 0.190 | 58% |
| `multinomial_v1` | 76 | 0.196 | 58% |
| `ordered_logit_v1` | 76 | 0.197 | 58% |
| `random_forest_v1` | 76 | 0.191 | 58% |
| `stack_v1` | 76 | 0.194 | 58% |
| `xgboost_v1` | 76 | 0.194 | 58% |

Results so far: football_data_co_uk 76.
