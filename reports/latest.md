# Latest predictions

Updated Sun 18 Oct 2026, 07:10 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sun 18 Oct 14:00 | Osasuna v Racing | 59% (48% to 69%) | 21% | 20% | Low, Low | 69% | 68% | 2.2 to 1.3 | 5.3 to 4.4 | 4.8 | manager_change, shape_v1, unanswered_question |
| Sun 18 Oct 15:00 | Bournemouth v Sunderland | 50% (43% to 58%) | 26% | 24% | Medium, Low | 51% | 56% | 1.6 to 1.1 | 5.3 to 4.7 | 3.9 | shape_v1, unanswered_question |
| Sun 18 Oct 15:00 | Brighton v Palace | 55% (47% to 62%) | 24% | 21% | Medium, Medium | 56% | 59% | 1.8 to 1.1 | 5.5 to 4.5 | 4.4 | shape_v1, unanswered_question |
| Sun 18 Oct 15:00 | Leeds v Man United | 34% (27% to 41%) | 26% | 40% | Low, Low | 55% | 61% | 1.3 to 1.5 | 4.5 to 5.8 | 4.7 | shape_v1, unanswered_question |
| Sun 18 Oct 16:15 | Celta v Alavés | 46% (40% to 53%) | 28% | 26% | Medium, Medium | 42% | 50% | 1.4 to 1.0 | 4.4 to 4.5 | 4.4 | shape_v1, unanswered_question |
| Sun 18 Oct 17:30 | Forest v Arsenal | 21% (16% to 26%) | 27% | 52% | Medium, Medium | 42% | 48% | 0.9 to 1.5 | 4.6 to 5.5 | 3.8 | shape_v1, unanswered_question |
| Sun 18 Oct 18:30 | Málaga v Sociedad | 27% (20% to 35%) | 27% | 46% | Low, Low | 46% | 53% | 1.0 to 1.4 | 4.6 to 5.1 | 5.1 | shape_v1, unanswered_question |
| Sun 18 Oct 21:00 | Real Madrid v Sevilla | 74% (68% to 80%) | 16% | 10% | Medium, Medium | 67% | 57% | 2.5 to 0.9 | 5.9 to 4.3 | 3.8 | shape_v1, unanswered_question |
| Mon 19 Oct 21:00 | Getafe v Rayo | 32% (26% to 37%) | 32% | 37% | Low, Medium | 32% | 43% | 1.0 to 1.0 | 4.5 to 4.9 | 6.2 | shape_v1, unanswered_question |
| Mon 19 Oct 21:00 | Tottenham v Coventry | 49% (39% to 60%) | 26% | 25% | Low, Low | 52% | 57% | 1.6 to 1.1 | 5.9 to 4.1 | 3.9 | shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 29 | 0.172 | 55% |
| `dc_bayes_v1_noshape` | 19 | 0.177 | 53% |
| `dc_mle_v0` | 29 | 0.185 | 52% |
| `elo_v0` | 29 | 0.168 | 52% |
| `multinomial_v1` | 29 | 0.179 | 52% |
| `ordered_logit_v1` | 29 | 0.183 | 48% |
| `random_forest_v1` | 29 | 0.170 | 52% |
| `stack_v1` | 29 | 0.175 | 52% |
| `xgboost_v1` | 29 | 0.172 | 52% |

Results so far: football_data_co_uk 19, football_data_org 10. 10 still wait for football-data.co.uk, so their corners and cards are scored only if Lang entered them.
