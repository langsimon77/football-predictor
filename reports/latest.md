# Latest predictions

Updated Sun 22 Nov 2026, 09:29 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sun 22 Nov 15:00 | Barcelona v Villarreal | 72% (65% to 79%) | 16% | 12% | Medium, Medium | 77% | 68% | 2.7 to 1.1 | 5.8 to 5.3 | 3.6 | shape_v1, unanswered_question |
| Sun 22 Nov 16:00 | Hull v Brighton | 19% (13% to 27%) | 25% | 56% | Low, Low | 52% | 55% | 1.0 to 1.7 | 4.7 to 5.3 | 4.0 | shape_v1, unanswered_question |
| Sun 22 Nov 17:15 | Racing v Sociedad | 33% (24% to 42%) | 24% | 44% | Low, Low | 69% | 72% | 1.6 to 1.8 | 4.5 to 6.1 | 4.6 | manager_change, shape_v1, unanswered_question |
| Sun 22 Nov 18:30 | Liverpool v Man United | 50% (43% to 58%) | 24% | 26% | Low, Low | 65% | 68% | 1.9 to 1.4 | 5.5 to 5.2 | 4.4 | manager_change, shape_v1, unanswered_question |
| Sun 22 Nov 19:30 | Osasuna v Málaga | 59% (50% to 67%) | 24% | 17% | Low, Low | 50% | 53% | 1.8 to 0.9 | 4.6 to 4.8 | 4.6 | shape_v1, unanswered_question |
| Sun 22 Nov 22:00 | Getafe v Atlético | 21% (17% to 26%) | 29% | 50% | Medium, Medium | 37% | 44% | 0.8 to 1.3 | 3.8 to 5.5 | 5.7 | shape_v1, unanswered_question |
| Mon 23 Nov 22:00 | Brentford v Everton | 42% (35% to 48%) | 27% | 31% | Low, Low | 50% | 57% | 1.4 to 1.2 | 4.8 to 5.1 | 3.8 | shape_v1, unanswered_question |
| Mon 23 Nov 22:00 | Levante v Elche | 45% (37% to 52%) | 27% | 29% | Medium, Low | 52% | 59% | 1.5 to 1.2 | 4.3 to 4.8 | 4.3 | shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 108 | 0.194 | 53% |
| `dc_bayes_v1_noshape` | 98 | 0.198 | 52% |
| `dc_mle_v0` | 108 | 0.198 | 55% |
| `elo_v0` | 108 | 0.194 | 55% |
| `multinomial_v1` | 108 | 0.196 | 55% |
| `ordered_logit_v1` | 108 | 0.197 | 54% |
| `random_forest_v1` | 108 | 0.194 | 55% |
| `stack_v1` | 108 | 0.195 | 55% |
| `xgboost_v1` | 108 | 0.195 | 55% |

Results so far: football_data_co_uk 96, football_data_org 12. 12 still wait for football-data.co.uk, so their corners and cards are scored only if Lang entered them.
