# Latest predictions

Updated Sat 24 Oct 2026, 07:03 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sat 24 Oct 13:30 | Aston Villa v Man City | 25% (19% to 31%) | 24% | 51% | Medium, Medium | 58% | 62% | 1.2 to 1.8 | 4.3 to 5.9 | 3.9 | shape_v1, unanswered_question, referee_unknown |
| Sat 24 Oct 16:00 | Arsenal v Everton | 64% (57% to 70%) | 23% | 13% | Medium, Medium | 43% | 44% | 1.7 to 0.7 | 5.4 to 4.5 | 3.4 | shape_v1, unanswered_question, referee_unknown |
| Sat 24 Oct 16:00 | Coventry v Fulham | 32% (23% to 41%) | 28% | 41% | Low, Low | 47% | 55% | 1.2 to 1.3 | 4.4 to 5.5 | 4.0 | shape_v1, unanswered_question, referee_unknown |
| Sat 24 Oct 18:30 | Chelsea v Tottenham | 52% (45% to 59%) | 24% | 25% | Medium, Medium | 62% | 65% | 1.9 to 1.3 | 5.0 to 5.4 | 4.6 | shape_v1, unanswered_question, referee_unknown |
| Sun 25 Oct 16:00 | Palace v Newcastle | 39% (33% to 46%) | 26% | 35% | Low, Medium | 58% | 64% | 1.5 to 1.4 | 4.4 to 5.5 | 4.0 | shape_v1, unanswered_question |
| Sun 25 Oct 16:00 | Hull v Brentford | 32% (23% to 42%) | 27% | 41% | Low, Low | 52% | 59% | 1.3 to 1.5 | 5.0 to 4.9 | 4.1 | shape_v1, unanswered_question |
| Sun 25 Oct 16:00 | Liverpool v Brighton | 46% (39% to 53%) | 25% | 29% | Medium, Medium | 61% | 65% | 1.7 to 1.4 | 5.6 to 4.9 | 4.0 | shape_v1, unanswered_question |
| Sun 25 Oct 16:00 | Man United v Bournemouth | 47% (40% to 54%) | 24% | 28% | Medium, Medium | 62% | 66% | 1.8 to 1.4 | 5.6 to 5.1 | 4.0 | shape_v1, unanswered_question |
| Sun 25 Oct 18:30 | Sunderland v Leeds | 37% (29% to 44%) | 29% | 34% | Low, Medium | 42% | 51% | 1.2 to 1.1 | 4.9 to 4.8 | 4.2 | shape_v1, unanswered_question |

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
