# Latest predictions

Updated Mon 19 Oct 2026, 07:21 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Mon 19 Oct 21:00 | Getafe v Rayo | 32% (26% to 37%) | 32% | 37% | Low, Medium | 32% | 43% | 1.0 to 1.0 | 4.5 to 4.9 | 6.2 | shape_v1, unanswered_question |
| Mon 19 Oct 21:00 | Tottenham v Coventry | 49% (39% to 60%) | 26% | 25% | Low, Low | 52% | 57% | 1.6 to 1.1 | 5.9 to 4.1 | 3.9 | shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 37 | 0.163 | 62% |
| `dc_bayes_v1_noshape` | 27 | 0.165 | 63% |
| `dc_mle_v0` | 37 | 0.174 | 59% |
| `elo_v0` | 37 | 0.161 | 59% |
| `multinomial_v1` | 37 | 0.170 | 59% |
| `ordered_logit_v1` | 37 | 0.170 | 57% |
| `random_forest_v1` | 37 | 0.162 | 59% |
| `stack_v1` | 37 | 0.166 | 59% |
| `xgboost_v1` | 37 | 0.163 | 59% |

Results so far: football_data_co_uk 19, football_data_org 18. 18 still wait for football-data.co.uk, so their corners and cards are scored only if Lang entered them.
