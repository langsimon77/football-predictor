# Latest predictions

Updated Sun 08 Nov 2026, 08:43 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sun 08 Nov 15:00 | Elche v Betis | 38% (31% to 45%) | 26% | 36% | Low, Medium | 58% | 64% | 1.5 to 1.5 | 4.7 to 4.7 | 4.4 | shape_v1, unanswered_question |
| Sun 08 Nov 16:00 | Brighton v Brentford | 54% (47% to 61%) | 24% | 22% | Medium, Medium | 58% | 61% | 1.8 to 1.1 | 5.3 to 4.8 | 3.8 | shape_v1, unanswered_question |
| Sun 08 Nov 16:00 | Sunderland v Chelsea | 32% (25% to 39%) | 27% | 42% | Low, Low | 53% | 60% | 1.3 to 1.5 | 4.5 to 5.4 | 4.2 | shape_v1, unanswered_question |
| Sun 08 Nov 16:00 | Ipswich v Bournemouth | 23% (16% to 30%) | 24% | 54% | Low, Medium | 62% | 64% | 1.2 to 1.9 | 4.2 to 5.7 | 4.2 | shape_v1, unanswered_question |
| Sun 08 Nov 16:00 | Palace v Liverpool | 27% (21% to 33%) | 26% | 48% | Medium, Medium | 56% | 61% | 1.2 to 1.7 | 3.8 to 6.2 | 3.9 | shape_v1, unanswered_question |
| Sun 08 Nov 17:15 | Sociedad v Rayo | 46% (39% to 53%) | 26% | 28% | Medium, Medium | 55% | 61% | 1.6 to 1.2 | 5.8 to 5.0 | 4.5 | shape_v1, unanswered_question |
| Sun 08 Nov 18:30 | Man United v Aston Villa | 51% (44% to 58%) | 24% | 25% | Medium, Medium | 61% | 64% | 1.8 to 1.3 | 5.6 to 4.7 | 4.1 | shape_v1, unanswered_question |
| Sun 08 Nov 19:30 | Celta v Levante | 50% (42% to 57%) | 26% | 24% | Medium, Low | 51% | 57% | 1.6 to 1.1 | 4.2 to 4.7 | 4.0 | shape_v1, unanswered_question |
| Sun 08 Nov 19:30 | Villarreal v Getafe | 62% (55% to 68%) | 24% | 14% | High, Medium | 43% | 44% | 1.7 to 0.7 | 5.3 to 4.1 | 4.4 | shape_v1 |
| Sun 08 Nov 22:00 | Atlético v Barcelona | 33% (27% to 40%) | 24% | 43% | Low, Medium | 69% | 72% | 1.6 to 1.8 | 5.0 to 5.5 | 4.1 | shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 86 | 0.190 | 55% |
| `dc_bayes_v1_noshape` | 76 | 0.195 | 54% |
| `dc_mle_v0` | 86 | 0.196 | 57% |
| `elo_v0` | 86 | 0.189 | 56% |
| `multinomial_v1` | 86 | 0.194 | 56% |
| `ordered_logit_v1` | 86 | 0.195 | 56% |
| `random_forest_v1` | 86 | 0.190 | 56% |
| `stack_v1` | 86 | 0.192 | 56% |
| `xgboost_v1` | 86 | 0.192 | 56% |

Results so far: football_data_co_uk 76, football_data_org 10. 10 still wait for football-data.co.uk, so their corners and cards are scored only if Lang entered them.
