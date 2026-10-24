# Latest predictions

Updated Sat 24 Oct 2026, 18:47 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sat 24 Oct 21:00 | Atlético v Deportivo | 69% (59% to 77%) | 19% | 12% | Medium, Low | 60% | 55% | 2.2 to 0.9 | 6.0 to 4.6 | 3.8 | late_lock, shape_v1 |
| Sun 25 Oct 15:00 | Athletic v Getafe | 54% (48% to 60%) | 28% | 17% | Medium, High | 32% | 38% | 1.3 to 0.7 | 5.6 to 3.8 | 4.6 | late_lock, shape_v1 |
| Sun 25 Oct 16:00 | Palace v Newcastle | 39% (33% to 46%) | 26% | 35% | Low, Medium | 58% | 64% | 1.5 to 1.4 | 4.4 to 5.5 | 4.0 | shape_v1, unanswered_question |
| Sun 25 Oct 16:00 | Hull v Brentford | 32% (23% to 42%) | 27% | 41% | Low, Low | 52% | 59% | 1.3 to 1.5 | 5.0 to 4.9 | 4.1 | shape_v1, unanswered_question |
| Sun 25 Oct 16:00 | Liverpool v Brighton | 46% (39% to 53%) | 25% | 29% | Medium, Medium | 61% | 65% | 1.7 to 1.4 | 5.6 to 4.9 | 4.0 | shape_v1, unanswered_question |
| Sun 25 Oct 16:00 | Man United v Bournemouth | 47% (40% to 54%) | 24% | 28% | Medium, Medium | 62% | 66% | 1.8 to 1.4 | 5.6 to 5.1 | 4.0 | shape_v1, unanswered_question |
| Sun 25 Oct 17:15 | Celta v Betis | 41% (34% to 47%) | 26% | 33% | Low, Medium | 56% | 62% | 1.5 to 1.4 | 4.3 to 4.6 | 4.4 | late_lock, shape_v1 |
| Sun 25 Oct 18:30 | Sunderland v Leeds | 37% (29% to 44%) | 29% | 34% | Low, Medium | 42% | 51% | 1.2 to 1.1 | 4.9 to 4.8 | 4.2 | shape_v1, unanswered_question |
| Sun 25 Oct 19:30 | Sociedad v Levante | 53% (45% to 60%) | 24% | 24% | Medium, Medium | 61% | 63% | 1.8 to 1.2 | 5.7 to 4.6 | 4.1 | shape_v1 |
| Sun 25 Oct 22:00 | Barcelona v Real Madrid | 57% (49% to 64%) | 20% | 23% | Medium, High | 78% | 76% | 2.4 to 1.6 | 5.8 to 5.1 | 4.6 | shape_v1 |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 41 | 0.164 | 59% |
| `dc_bayes_v1_noshape` | 31 | 0.166 | 58% |
| `dc_mle_v0` | 41 | 0.173 | 59% |
| `elo_v0` | 41 | 0.163 | 56% |
| `multinomial_v1` | 41 | 0.169 | 59% |
| `ordered_logit_v1` | 41 | 0.170 | 56% |
| `random_forest_v1` | 41 | 0.163 | 56% |
| `stack_v1` | 41 | 0.166 | 56% |
| `xgboost_v1` | 41 | 0.164 | 56% |

Results so far: football_data_co_uk 40, football_data_org 1. 1 still wait for football-data.co.uk, so their corners and cards are scored only if Lang entered them.
