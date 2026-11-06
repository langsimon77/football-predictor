# Latest predictions

Updated Fri 06 Nov 2026, 09:25 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Fri 06 Nov 22:00 | Sevilla v Alavés | 44% (38% to 50%) | 28% | 28% | Low, Medium | 44% | 53% | 1.4 to 1.1 | 4.7 to 4.4 | 4.9 | shape_v1, unanswered_question |
| Fri 06 Nov 22:00 | Everton v Coventry | 51% (41% to 60%) | 27% | 22% | Low, Low | 45% | 51% | 1.5 to 1.0 | 4.9 to 4.9 | 3.6 | shape_v1, unanswered_question, referee_unknown |
| Sat 07 Nov 14:30 | Leeds v Tottenham | 41% (33% to 48%) | 28% | 32% | Low, Low | 48% | 56% | 1.4 to 1.2 | 4.0 to 6.2 | 4.1 | shape_v1, unanswered_question, referee_unknown |
| Sat 07 Nov 15:00 | Málaga v Racing | 43% (31% to 55%) | 25% | 32% | Low, Low | 62% | 67% | 1.7 to 1.5 | 5.3 to 4.8 | 4.6 | manager_change, shape_v1, unanswered_question |
| Sat 07 Nov 17:00 | Arsenal v Hull | 74% (65% to 82%) | 18% | 8% | Medium, Low | 48% | 39% | 2.0 to 0.6 | 5.6 to 4.4 | 3.3 | shape_v1, unanswered_question, referee_unknown |
| Sat 07 Nov 17:00 | Fulham v Newcastle | 43% (36% to 50%) | 27% | 30% | Low, Low | 54% | 60% | 1.5 to 1.3 | 5.4 to 4.9 | 4.0 | shape_v1, unanswered_question, referee_unknown |
| Sat 07 Nov 17:15 | Espanyol v Deportivo | 39% (30% to 48%) | 28% | 33% | Low, Low | 46% | 55% | 1.3 to 1.2 | 4.1 to 5.5 | 4.7 | manager_change, shape_v1, unanswered_question |
| Sat 07 Nov 19:30 | Osasuna v Athletic | 35% (29% to 42%) | 29% | 36% | Low, Low | 43% | 53% | 1.2 to 1.2 | 3.9 to 5.5 | 6.0 | manager_change, shape_v1, unanswered_question |
| Sat 07 Nov 19:30 | Forest v Man City | 23% (18% to 29%) | 26% | 51% | Medium, Low | 52% | 57% | 1.1 to 1.6 | 4.6 to 5.9 | 3.8 | shape_v1, unanswered_question, referee_unknown |
| Sat 07 Nov 22:00 | Valencia v Real Madrid | 17% (13% to 22%) | 23% | 60% | Medium, Low | 54% | 55% | 0.9 to 1.9 | 4.2 to 5.8 | 3.9 | shape_v1, unanswered_question |

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
