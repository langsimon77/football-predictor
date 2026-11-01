# Latest predictions

Updated Sun 01 Nov 2026, 08:52 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sun 01 Nov 15:00 | Getafe v Sevilla | 34% (28% to 39%) | 32% | 34% | Low, Medium | 30% | 42% | 1.0 to 1.0 | 4.0 to 4.6 | 5.1 | shape_v1, unanswered_question |
| Sun 01 Nov 17:15 | Racing v Real Madrid | 13% (8% to 20%) | 16% | 71% | Medium, Medium | 82% | 73% | 1.3 to 2.9 | 4.3 to 6.4 | 3.9 | shape_v1, unanswered_question |
| Sun 01 Nov 18:30 | Liverpool v Arsenal | 31% (25% to 38%) | 28% | 41% | Low, Low | 46% | 54% | 1.1 to 1.3 | 5.1 to 5.0 | 4.0 | shape_v1, unanswered_question |
| Sun 01 Nov 19:30 | Elche v Valencia | 50% (43% to 57%) | 27% | 23% | Medium, Medium | 42% | 49% | 1.4 to 0.9 | 4.6 to 4.4 | 4.6 | shape_v1, unanswered_question |
| Sun 01 Nov 22:00 | Athletic v Sociedad | 49% (43% to 56%) | 26% | 25% | Medium, Low | 51% | 57% | 1.6 to 1.1 | 5.3 to 4.8 | 5.6 | shape_v1, unanswered_question |
| Mon 02 Nov 22:00 | Deportivo v Osasuna | 45% (35% to 54%) | 28% | 27% | Low, Low | 46% | 54% | 1.4 to 1.1 | 5.0 to 4.4 | 4.6 | manager_change, shape_v1, unanswered_question |
| Mon 02 Nov 22:00 | Newcastle v Everton | 45% (38% to 52%) | 26% | 29% | Medium, Low | 54% | 60% | 1.6 to 1.2 | 5.3 to 4.7 | 3.9 | shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 69 | 0.187 | 57% |
| `dc_bayes_v1_noshape` | 59 | 0.192 | 56% |
| `dc_mle_v0` | 69 | 0.194 | 58% |
| `elo_v0` | 69 | 0.186 | 57% |
| `multinomial_v1` | 69 | 0.192 | 58% |
| `ordered_logit_v1` | 69 | 0.194 | 57% |
| `random_forest_v1` | 69 | 0.188 | 57% |
| `stack_v1` | 69 | 0.190 | 57% |
| `xgboost_v1` | 69 | 0.190 | 57% |

Results so far: football_data_co_uk 56, football_data_org 13. 13 still wait for football-data.co.uk, so their corners and cards are scored only if Lang entered them.
