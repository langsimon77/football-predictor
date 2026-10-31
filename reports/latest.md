# Latest predictions

Updated Sat 31 Oct 2026, 08:19 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sat 31 Oct 14:30 | Chelsea v Man United | 41% (34% to 48%) | 24% | 34% | Low, Medium | 66% | 70% | 1.7 to 1.6 | 5.1 to 5.3 | 4.0 | shape_v1, unanswered_question, referee_unknown |
| Sat 31 Oct 15:00 | Levante v Atlético | 28% (22% to 35%) | 25% | 46% | Medium, Medium | 58% | 63% | 1.3 to 1.7 | 4.2 to 5.9 | 4.0 | shape_v1, unanswered_question |
| Sat 31 Oct 17:00 | Brentford v Forest | 42% (35% to 49%) | 27% | 31% | Low, Low | 52% | 59% | 1.5 to 1.3 | 4.6 to 5.6 | 3.9 | shape_v1, unanswered_question, referee_unknown |
| Sat 31 Oct 17:00 | Bournemouth v Leeds | 48% (41% to 56%) | 26% | 26% | Medium, Low | 53% | 59% | 1.6 to 1.2 | 5.4 to 4.7 | 3.9 | shape_v1, unanswered_question, referee_unknown |
| Sat 31 Oct 17:00 | Man City v Brighton | 55% (47% to 62%) | 23% | 22% | Medium, Medium | 60% | 62% | 1.9 to 1.2 | 5.9 to 4.6 | 3.7 | shape_v1, unanswered_question, referee_unknown |
| Sat 31 Oct 17:00 | Coventry v Sunderland | 33% (25% to 43%) | 30% | 37% | Low, Low | 40% | 49% | 1.1 to 1.2 | 4.7 to 4.9 | 3.9 | shape_v1, unanswered_question, referee_unknown |
| Sat 31 Oct 17:00 | Hull v Ipswich | 44% (34% to 55%) | 26% | 29% | Low, Low | 53% | 59% | 1.5 to 1.2 | 5.0 to 4.6 | 3.9 | shape_v1, unanswered_question, referee_unknown |
| Sat 31 Oct 17:15 | Rayo v Celta | 46% (39% to 52%) | 27% | 27% | Medium, Low | 48% | 55% | 1.5 to 1.1 | 4.9 to 4.4 | 4.6 | shape_v1 |
| Sat 31 Oct 19:30 | Betis v Málaga | 74% (65% to 82%) | 17% | 10% | Medium, Medium | 64% | 55% | 2.4 to 0.8 | 5.0 to 5.2 | 5.0 | shape_v1 |
| Sat 31 Oct 19:30 | Tottenham v Palace | 45% (39% to 52%) | 26% | 28% | Medium, Low | 52% | 59% | 1.5 to 1.2 | 5.9 to 4.1 | 4.0 | shape_v1, unanswered_question, referee_unknown |
| Sat 31 Oct 22:00 | Barcelona v Alavés | 78% (71% to 83%) | 14% | 8% | High, High | 71% | 57% | 2.7 to 0.9 | 6.6 to 4.5 | 3.6 | shape_v1 |
| Sat 31 Oct 22:00 | Aston Villa v Fulham | 43% (37% to 50%) | 27% | 30% | Low, Low | 50% | 57% | 1.5 to 1.2 | 4.6 to 5.5 | 3.8 | shape_v1, unanswered_question, referee_unknown |
| Sun 01 Nov 15:00 | Getafe v Sevilla | 34% (28% to 39%) | 32% | 34% | Low, Medium | 30% | 42% | 1.0 to 1.0 | 4.0 to 4.6 | 5.1 | shape_v1, unanswered_question |
| Sun 01 Nov 17:15 | Racing v Real Madrid | 13% (8% to 20%) | 16% | 71% | Medium, Medium | 82% | 73% | 1.3 to 2.9 | 4.3 to 6.4 | 3.9 | shape_v1, unanswered_question |
| Sun 01 Nov 18:30 | Liverpool v Arsenal | 31% (25% to 38%) | 28% | 41% | Low, Low | 46% | 54% | 1.1 to 1.3 | 5.1 to 5.0 | 4.0 | shape_v1, unanswered_question |
| Sun 01 Nov 19:30 | Elche v Valencia | 50% (43% to 57%) | 27% | 23% | Medium, Medium | 42% | 49% | 1.4 to 0.9 | 4.6 to 4.4 | 4.6 | shape_v1, unanswered_question |
| Sun 01 Nov 22:00 | Athletic v Sociedad | 49% (43% to 56%) | 26% | 25% | Medium, Low | 51% | 57% | 1.6 to 1.1 | 5.3 to 4.8 | 5.6 | shape_v1, unanswered_question |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 57 | 0.187 | 54% |
| `dc_bayes_v1_noshape` | 47 | 0.192 | 53% |
| `dc_mle_v0` | 57 | 0.193 | 56% |
| `elo_v0` | 57 | 0.187 | 53% |
| `multinomial_v1` | 57 | 0.192 | 56% |
| `ordered_logit_v1` | 57 | 0.193 | 54% |
| `random_forest_v1` | 57 | 0.189 | 54% |
| `stack_v1` | 57 | 0.191 | 54% |
| `xgboost_v1` | 57 | 0.191 | 53% |

Results so far: football_data_co_uk 56, football_data_org 1. 1 still wait for football-data.co.uk, so their corners and cards are scored only if Lang entered them.
