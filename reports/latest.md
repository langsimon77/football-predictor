# Latest predictions

Updated Sat 07 Nov 2026, 08:37 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sat 07 Nov 14:30 | Leeds v Tottenham | 41% (33% to 48%) | 28% | 32% | Low, Low | 48% | 56% | 1.4 to 1.2 | 4.0 to 6.2 | 4.1 | shape_v1, unanswered_question, referee_unknown |
| Sat 07 Nov 15:00 | Málaga v Racing | 43% (31% to 55%) | 25% | 32% | Low, Low | 62% | 67% | 1.7 to 1.5 | 5.3 to 4.8 | 4.6 | manager_change, shape_v1, unanswered_question |
| Sat 07 Nov 17:00 | Fulham v Newcastle | 43% (36% to 50%) | 27% | 30% | Low, Low | 54% | 60% | 1.5 to 1.3 | 5.4 to 4.9 | 4.0 | shape_v1, unanswered_question, referee_unknown |
| Sat 07 Nov 17:00 | Arsenal v Hull | 74% (65% to 82%) | 18% | 8% | Medium, Low | 48% | 39% | 2.0 to 0.6 | 5.6 to 4.4 | 3.3 | shape_v1, unanswered_question, referee_unknown |
| Sat 07 Nov 17:15 | Espanyol v Deportivo | 39% (30% to 48%) | 28% | 33% | Low, Low | 46% | 55% | 1.3 to 1.2 | 4.1 to 5.5 | 4.7 | manager_change, shape_v1, unanswered_question |
| Sat 07 Nov 19:30 | Forest v Man City | 23% (18% to 29%) | 26% | 51% | Medium, Low | 52% | 57% | 1.1 to 1.6 | 4.6 to 5.9 | 3.8 | shape_v1, unanswered_question, referee_unknown |
| Sat 07 Nov 19:30 | Osasuna v Athletic | 35% (29% to 42%) | 29% | 36% | Low, Low | 43% | 53% | 1.2 to 1.2 | 3.9 to 5.5 | 6.0 | manager_change, shape_v1, unanswered_question |
| Sat 07 Nov 22:00 | Valencia v Real Madrid | 17% (13% to 22%) | 23% | 60% | Medium, Low | 54% | 55% | 0.9 to 1.9 | 4.2 to 5.8 | 3.9 | shape_v1, unanswered_question |
| Sun 08 Nov 15:00 | Elche v Betis | 38% (31% to 45%) | 26% | 36% | Low, Medium | 58% | 64% | 1.5 to 1.5 | 4.7 to 4.7 | 4.4 | shape_v1, unanswered_question |
| Sun 08 Nov 16:00 | Brighton v Brentford | 54% (47% to 61%) | 24% | 22% | Medium, Medium | 58% | 61% | 1.8 to 1.1 | 5.3 to 4.8 | 3.8 | shape_v1, unanswered_question |
| Sun 08 Nov 16:00 | Palace v Liverpool | 27% (21% to 33%) | 26% | 48% | Medium, Medium | 56% | 61% | 1.2 to 1.7 | 3.8 to 6.2 | 3.9 | shape_v1, unanswered_question |
| Sun 08 Nov 16:00 | Sunderland v Chelsea | 32% (25% to 39%) | 27% | 42% | Low, Low | 53% | 60% | 1.3 to 1.5 | 4.5 to 5.4 | 4.2 | shape_v1, unanswered_question |
| Sun 08 Nov 16:00 | Ipswich v Bournemouth | 23% (16% to 30%) | 24% | 54% | Low, Medium | 62% | 64% | 1.2 to 1.9 | 4.2 to 5.7 | 4.2 | shape_v1, unanswered_question |
| Sun 08 Nov 17:15 | Sociedad v Rayo | 46% (39% to 53%) | 26% | 28% | Medium, Medium | 55% | 61% | 1.6 to 1.2 | 5.8 to 5.0 | 4.5 | shape_v1, unanswered_question |
| Sun 08 Nov 18:30 | Man United v Aston Villa | 51% (44% to 58%) | 24% | 25% | Medium, Medium | 61% | 64% | 1.8 to 1.3 | 5.6 to 4.7 | 4.1 | shape_v1, unanswered_question |
| Sun 08 Nov 19:30 | Villarreal v Getafe | 62% (55% to 68%) | 24% | 14% | High, Medium | 43% | 44% | 1.7 to 0.7 | 5.3 to 4.1 | 4.4 | shape_v1 |
| Sun 08 Nov 19:30 | Celta v Levante | 50% (42% to 57%) | 26% | 24% | Medium, Low | 51% | 57% | 1.6 to 1.1 | 4.2 to 4.7 | 4.0 | shape_v1, unanswered_question |
| Sun 08 Nov 22:00 | Atlético v Barcelona | 33% (27% to 40%) | 24% | 43% | Low, Medium | 69% | 72% | 1.6 to 1.8 | 5.0 to 5.5 | 4.1 | shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 78 | 0.191 | 56% |
| `dc_bayes_v1_noshape` | 68 | 0.195 | 56% |
| `dc_mle_v0` | 78 | 0.196 | 59% |
| `elo_v0` | 78 | 0.188 | 58% |
| `multinomial_v1` | 78 | 0.194 | 58% |
| `ordered_logit_v1` | 78 | 0.195 | 58% |
| `random_forest_v1` | 78 | 0.189 | 58% |
| `stack_v1` | 78 | 0.192 | 58% |
| `xgboost_v1` | 78 | 0.192 | 58% |

Results so far: football_data_co_uk 76, football_data_org 2. 2 still wait for football-data.co.uk, so their corners and cards are scored only if Lang entered them.
