# Latest predictions

Updated Mon 23 Nov 2026, 10:15 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Mon 23 Nov 22:00 | Brentford v Everton | 42% (35% to 48%) | 27% | 31% | Low, Low | 50% | 57% | 1.4 to 1.2 | 4.8 to 5.1 | 3.8 | shape_v1, unanswered_question |
| Mon 23 Nov 22:00 | Levante v Elche | 45% (37% to 52%) | 27% | 29% | Medium, Low | 52% | 59% | 1.5 to 1.2 | 4.3 to 4.8 | 4.3 | shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 114 | 0.195 | 54% |
| `dc_bayes_v1_noshape` | 104 | 0.199 | 53% |
| `dc_mle_v0` | 114 | 0.198 | 55% |
| `elo_v0` | 114 | 0.194 | 55% |
| `multinomial_v1` | 114 | 0.197 | 55% |
| `ordered_logit_v1` | 114 | 0.197 | 54% |
| `random_forest_v1` | 114 | 0.195 | 55% |
| `stack_v1` | 114 | 0.196 | 55% |
| `xgboost_v1` | 114 | 0.196 | 55% |

Results so far: football_data_co_uk 96, football_data_org 18. 18 still wait for football-data.co.uk, so their corners and cards are scored only if Lang entered them.
