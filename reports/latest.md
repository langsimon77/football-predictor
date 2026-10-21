# Latest predictions

Updated Wed 21 Oct 2026, 07:20 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Wed 21 Oct 20:00 | Levante v Athletic | 36% (29% to 43%) | 27% | 37% | Low, Low | 50% | 57% | 1.3 to 1.3 | 4.2 to 5.6 | 4.4 | shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 39 | 0.162 | 62% |
| `dc_bayes_v1_noshape` | 29 | 0.163 | 62% |
| `dc_mle_v0` | 39 | 0.172 | 59% |
| `elo_v0` | 39 | 0.160 | 59% |
| `multinomial_v1` | 39 | 0.167 | 62% |
| `ordered_logit_v1` | 39 | 0.168 | 56% |
| `random_forest_v1` | 39 | 0.161 | 59% |
| `stack_v1` | 39 | 0.164 | 59% |
| `xgboost_v1` | 39 | 0.162 | 59% |

Results so far: football_data_co_uk 39.
