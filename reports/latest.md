# Latest predictions

Updated Fri 27 Nov 2026, 11:06 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Fri 27 Nov 22:00 | Forest v Chelsea | 39% (32% to 45%) | 27% | 35% | Low, Medium | 55% | 62% | 1.5 to 1.4 | 4.8 to 5.4 | 4.3 | shape_v1, unanswered_question, referee_unknown |
| Fri 27 Nov 22:00 | Levante v Racing | 56% (46% to 67%) | 22% | 22% | Low, Low | 71% | 71% | 2.2 to 1.4 | 5.8 to 4.7 | 4.2 | manager_change, shape_v1, unanswered_question |
| Sat 28 Nov 15:00 | Betis v Rayo | 52% (45% to 59%) | 24% | 24% | Medium, Medium | 59% | 62% | 1.8 to 1.2 | 5.4 to 5.7 | 4.0 | shape_v1, unanswered_question |
| Sat 28 Nov 17:00 | Leeds v Coventry | 54% (44% to 64%) | 25% | 21% | Low, Low | 52% | 56% | 1.7 to 1.0 | 5.0 to 4.8 | 3.7 | shape_v1, unanswered_question, referee_unknown |
| Sat 28 Nov 17:00 | Man United v Brentford | 51% (43% to 58%) | 24% | 25% | Low, Low | 63% | 66% | 1.9 to 1.3 | 5.7 to 4.7 | 3.9 | manager_change, shape_v1, unanswered_question, referee_unknown |
| Sat 28 Nov 17:15 | Málaga v Athletic | 24% (18% to 31%) | 28% | 48% | Low, Low | 43% | 50% | 0.9 to 1.4 | 4.2 to 5.5 | 4.6 | shape_v1, unanswered_question |
| Sat 28 Nov 19:30 | Elche v Atlético | 26% (20% to 33%) | 26% | 47% | Medium, Low | 52% | 58% | 1.1 to 1.6 | 4.0 to 5.4 | 4.2 | shape_v1, unanswered_question |
| Sat 28 Nov 19:30 | Ipswich v Aston Villa | 27% (20% to 34%) | 25% | 49% | Low, Medium | 59% | 64% | 1.3 to 1.7 | 4.4 to 5.4 | 4.1 | shape_v1, unanswered_question, referee_unknown |
| Sat 28 Nov 22:00 | Real Madrid v Alavés | 74% (67% to 79%) | 17% | 10% | Medium, Medium | 66% | 56% | 2.4 to 0.9 | 5.9 to 4.6 | 3.7 | shape_v1, unanswered_question |

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
