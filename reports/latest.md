# Latest predictions

Updated Sat 28 Nov 2026, 10:28 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sat 28 Nov 15:00 | Betis v Rayo | 52% (45% to 59%) | 24% | 24% | Medium, Medium | 59% | 62% | 1.8 to 1.2 | 5.4 to 5.7 | 4.0 | shape_v1, unanswered_question |
| Sat 28 Nov 17:00 | Leeds v Coventry | 54% (44% to 64%) | 25% | 21% | Low, Low | 52% | 56% | 1.7 to 1.0 | 5.0 to 4.8 | 3.7 | shape_v1, unanswered_question, referee_unknown |
| Sat 28 Nov 17:00 | Man United v Brentford | 51% (43% to 58%) | 24% | 25% | Low, Low | 63% | 66% | 1.9 to 1.3 | 5.7 to 4.7 | 3.9 | manager_change, shape_v1, unanswered_question, referee_unknown |
| Sat 28 Nov 17:15 | Málaga v Athletic | 24% (18% to 31%) | 28% | 48% | Low, Low | 43% | 50% | 0.9 to 1.4 | 4.2 to 5.5 | 4.6 | shape_v1, unanswered_question |
| Sat 28 Nov 19:30 | Ipswich v Aston Villa | 27% (20% to 34%) | 25% | 49% | Low, Medium | 59% | 64% | 1.3 to 1.7 | 4.4 to 5.4 | 4.1 | shape_v1, unanswered_question, referee_unknown |
| Sat 28 Nov 19:30 | Elche v Atlético | 26% (20% to 33%) | 26% | 47% | Medium, Low | 52% | 58% | 1.1 to 1.6 | 4.0 to 5.4 | 4.2 | shape_v1, unanswered_question |
| Sat 28 Nov 22:00 | Real Madrid v Alavés | 74% (67% to 79%) | 17% | 10% | Medium, Medium | 66% | 56% | 2.4 to 0.9 | 5.9 to 4.6 | 3.7 | shape_v1, unanswered_question |
| Sun 29 Nov 14:00 | Everton v Liverpool | 29% (23% to 35%) | 27% | 45% | Medium, Low | 53% | 59% | 1.2 to 1.5 | 4.2 to 6.1 | 4.4 | shape_v1, unanswered_question |
| Sun 29 Nov 15:00 | Valencia v Osasuna | 39% (33% to 45%) | 31% | 30% | Low, Medium | 36% | 46% | 1.2 to 1.0 | 4.5 to 4.7 | 4.7 | shape_v1, unanswered_question |
| Sun 29 Nov 16:05 | Brighton v Newcastle | 55% (48% to 62%) | 23% | 21% | Medium, Medium | 61% | 63% | 1.9 to 1.2 | 5.1 to 5.1 | 4.1 | shape_v1, unanswered_question |
| Sun 29 Nov 16:05 | Palace v Hull | 52% (43% to 62%) | 25% | 22% | Low, Low | 52% | 57% | 1.7 to 1.1 | 4.5 to 5.1 | 3.9 | manager_change, shape_v1, unanswered_question |
| Sun 29 Nov 16:05 | Fulham v Bournemouth | 36% (30% to 43%) | 28% | 36% | Low, Low | 49% | 57% | 1.3 to 1.3 | 5.1 to 5.2 | 4.2 | shape_v1, unanswered_question |
| Sun 29 Nov 16:05 | Sunderland v Tottenham | 35% (28% to 42%) | 29% | 36% | Low, Medium | 43% | 52% | 1.2 to 1.2 | 4.0 to 6.0 | 4.3 | shape_v1, unanswered_question |
| Sun 29 Nov 17:15 | Deportivo v Barcelona | 14% (9% to 20%) | 19% | 68% | Medium, Medium | 69% | 64% | 1.1 to 2.4 | 4.6 to 6.4 | 3.8 | shape_v1, unanswered_question |
| Sun 29 Nov 18:30 | Arsenal v Man City | 47% (40% to 54%) | 28% | 25% | Medium, Medium | 43% | 51% | 1.4 to 1.0 | 4.7 to 5.6 | 3.9 | shape_v1, unanswered_question |
| Sun 29 Nov 19:30 | Celta v Villarreal | 37% (30% to 43%) | 28% | 36% | Low, Low | 51% | 58% | 1.3 to 1.3 | 3.9 to 4.9 | 4.5 | shape_v1, unanswered_question |
| Sun 29 Nov 22:00 | Sociedad v Sevilla | 48% (41% to 55%) | 26% | 26% | Medium, Low | 52% | 58% | 1.6 to 1.1 | 5.3 to 4.7 | 4.7 | shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 118 | 0.197 | 53% |
| `dc_bayes_v1_noshape` | 108 | 0.201 | 53% |
| `dc_bayes_xg_blend_v1` | 2 | 0.338 | 50% |
| `dc_bayes_xg_joint_v1` | 2 | 0.335 | 50% |
| `dc_mle_v0` | 118 | 0.200 | 55% |
| `elo_v0` | 118 | 0.196 | 55% |
| `multinomial_v1` | 118 | 0.199 | 55% |
| `ordered_logit_v1` | 118 | 0.200 | 54% |
| `random_forest_v1` | 118 | 0.197 | 55% |
| `stack_v1` | 118 | 0.198 | 55% |
| `xgboost_v1` | 118 | 0.198 | 55% |

Results so far: football_data_co_uk 116, football_data_org 2. 2 still wait for football-data.co.uk, so their corners and cards are scored only if Lang entered them.
