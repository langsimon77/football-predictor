# Latest predictions

Updated Fri 16 Oct 2026, 07:01 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Fri 16 Oct 21:00 | Deportivo v Levante | 45% (35% to 56%) | 26% | 29% | Low, Low | 56% | 61% | 1.6 to 1.3 | 5.2 to 4.8 | 4.2 | shape_v1, unanswered_question |
| Sat 17 Oct 13:30 | Everton v Chelsea | 36% (30% to 43%) | 26% | 37% | Low, Low | 55% | 61% | 1.4 to 1.4 | 4.6 to 5.4 | 3.9 | shape_v1, unanswered_question, referee_unknown |
| Sat 17 Oct 14:00 | Espanyol v Atlético | 25% (19% to 31%) | 25% | 50% | Medium, Low | 54% | 59% | 1.1 to 1.7 | 3.9 to 5.9 | 4.6 | shape_v1, unanswered_question |
| Sat 17 Oct 16:00 | Brentford v Liverpool | 31% (25% to 38%) | 25% | 44% | Low, Medium | 62% | 66% | 1.4 to 1.7 | 4.4 to 5.8 | 4.2 | shape_v1, unanswered_question, referee_unknown |
| Sat 17 Oct 16:00 | Man City v Ipswich | 81% (73% to 87%) | 13% | 7% | Medium, Medium | 73% | 55% | 2.8 to 0.8 | 6.5 to 3.8 | 3.3 | shape_v1, unanswered_question, referee_unknown |
| Sat 17 Oct 16:00 | Fulham v Hull | 49% (39% to 59%) | 26% | 25% | Low, Low | 49% | 55% | 1.5 to 1.1 | 5.3 to 4.7 | 3.7 | shape_v1, unanswered_question, referee_unknown |
| Sat 17 Oct 16:15 | Villarreal v Elche | 60% (53% to 67%) | 22% | 18% | Medium, Medium | 60% | 60% | 2.0 to 1.1 | 4.9 to 4.5 | 4.1 | shape_v1, unanswered_question |
| Sat 17 Oct 18:30 | Newcastle v Aston Villa | 44% (37% to 52%) | 25% | 31% | Medium, Medium | 63% | 67% | 1.7 to 1.4 | 5.3 to 4.8 | 4.0 | shape_v1, unanswered_question, referee_unknown |
| Sat 17 Oct 18:30 | Betis v Barcelona | 26% (20% to 32%) | 22% | 52% | Medium, Medium | 73% | 73% | 1.5 to 2.1 | 4.3 to 6.7 | 3.9 | shape_v1, unanswered_question |
| Sat 17 Oct 21:00 | Valencia v Athletic | 32% (26% to 38%) | 30% | 38% | Low, Medium | 37% | 47% | 1.0 to 1.2 | 4.3 to 5.3 | 4.4 | shape_v1, unanswered_question |

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
