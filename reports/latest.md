# Latest predictions

Updated Fri 23 Oct 2026, 07:24 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Fri 23 Oct 21:00 | Ipswich v Forest | 29% (21% to 37%) | 26% | 46% | Low, Low | 55% | 61% | 1.2 to 1.6 | 4.4 to 5.6 | 4.2 | shape_v1, unanswered_question, corners_total_posterior_fallback, referee_unknown |
| Sat 24 Oct 13:30 | Aston Villa v Man City | 25% (19% to 31%) | 24% | 51% | Medium, Medium | 58% | 62% | 1.2 to 1.8 | 4.3 to 5.9 | 3.9 | shape_v1, unanswered_question, referee_unknown |
| Sat 24 Oct 16:00 | Coventry v Fulham | 32% (23% to 41%) | 28% | 41% | Low, Low | 47% | 55% | 1.2 to 1.3 | 4.4 to 5.5 | 4.0 | shape_v1, unanswered_question, referee_unknown |
| Sat 24 Oct 16:00 | Arsenal v Everton | 64% (57% to 70%) | 23% | 13% | Medium, Medium | 43% | 44% | 1.7 to 0.7 | 5.4 to 4.5 | 3.4 | shape_v1, unanswered_question, referee_unknown |
| Sat 24 Oct 18:30 | Chelsea v Tottenham | 52% (45% to 59%) | 24% | 25% | Medium, Medium | 62% | 65% | 1.9 to 1.3 | 5.0 to 5.4 | 4.6 | shape_v1, unanswered_question, referee_unknown |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 40 | 0.165 | 60% |
| `dc_bayes_v1_noshape` | 30 | 0.167 | 60% |
| `dc_mle_v0` | 40 | 0.174 | 60% |
| `elo_v0` | 40 | 0.163 | 57% |
| `multinomial_v1` | 40 | 0.170 | 60% |
| `ordered_logit_v1` | 40 | 0.170 | 57% |
| `random_forest_v1` | 40 | 0.164 | 57% |
| `stack_v1` | 40 | 0.167 | 57% |
| `xgboost_v1` | 40 | 0.165 | 57% |

Results so far: football_data_co_uk 40.
