# Latest predictions

Updated Fri 20 Nov 2026, 09:46 Juba time. Primary model: `dc_bayes_v1` (Bayesian Dixon-Coles with shots on target). Probabilities are locked and never edited. The range after the home-win chance is the model's 80% interval. Tier: how far to trust the home, draw, away forecast, then over 2.5 goals (High, Medium, Low; see `docs/LEARN.md` chapter 4).

## Locked, not yet played

| Kickoff (Juba) | Match | Home (80% range) | Draw | Away | Tier | Over 2.5 | BTTS | Exp. goals | Exp. corners | Exp. yellows | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Fri 20 Nov 22:00 | Athletic v Espanyol | 57% (50% to 63%) | 25% | 18% | Low, Low | 45% | 49% | 1.6 to 0.8 | 5.7 to 4.1 | 4.5 | manager_change, shape_v1, unanswered_question |
| Sat 21 Nov 14:30 | Man City v Fulham | 62% (54% to 69%) | 22% | 16% | Medium, Low | 55% | 55% | 1.9 to 0.9 | 5.8 to 4.7 | 3.5 | shape_v1, unanswered_question, referee_unknown |
| Sat 21 Nov 15:00 | Alavés v Deportivo | 47% (38% to 56%) | 28% | 25% | Low, Low | 42% | 50% | 1.4 to 1.0 | 4.7 to 5.0 | 4.5 | shape_v1, unanswered_question |
| Sat 21 Nov 17:00 | Bournemouth v Forest | 48% (41% to 55%) | 26% | 25% | Medium, Low | 51% | 57% | 1.6 to 1.1 | 5.3 to 5.0 | 4.0 | shape_v1, unanswered_question, referee_unknown |
| Sat 21 Nov 17:00 | Aston Villa v Sunderland | 48% (41% to 55%) | 27% | 25% | Medium, Low | 48% | 55% | 1.5 to 1.1 | 4.8 to 5.0 | 3.8 | shape_v1, unanswered_question, referee_unknown |
| Sat 21 Nov 17:00 | Tottenham v Ipswich | 60% (52% to 68%) | 22% | 17% | Low, Medium | 59% | 59% | 2.0 to 1.0 | 6.5 to 3.6 | 3.9 | shape_v1, unanswered_question, referee_unknown |
| Sat 21 Nov 17:00 | Coventry v Palace | 36% (27% to 45%) | 27% | 37% | Low, Low | 51% | 59% | 1.3 to 1.4 | 5.3 to 4.3 | 3.9 | manager_change, shape_v1, unanswered_question, referee_unknown |
| Sat 21 Nov 17:00 | Chelsea v Leeds | 50% (42% to 57%) | 25% | 25% | Medium, Medium | 56% | 61% | 1.7 to 1.2 | 5.4 to 4.6 | 3.9 | shape_v1, unanswered_question, referee_unknown |
| Sat 21 Nov 17:15 | Rayo v Valencia | 55% (48% to 61%) | 26% | 19% | Medium, Medium | 43% | 48% | 1.5 to 0.8 | 5.2 to 4.9 | 4.5 | shape_v1 |
| Sat 21 Nov 19:30 | Sevilla v Betis | 37% (30% to 44%) | 27% | 36% | Low, Medium | 55% | 62% | 1.4 to 1.4 | 4.9 to 4.6 | 5.8 | shape_v1, unanswered_question |
| Sat 21 Nov 19:30 | Newcastle v Arsenal | 20% (15% to 26%) | 26% | 54% | Medium, Low | 47% | 52% | 0.9 to 1.6 | 4.6 to 5.4 | 4.0 | shape_v1, unanswered_question, referee_unknown |
| Sat 21 Nov 22:00 | Real Madrid v Celta | 74% (68% to 80%) | 16% | 10% | High, High | 66% | 56% | 2.4 to 0.9 | 5.7 to 3.9 | 3.5 | shape_v1 |

## Scored so far

Lower RPS is better; 0 is perfect.

| Model | Matches | Mean RPS | Top pick right |
|---|---|---|---|
| `dc_bayes_v1` | 96 | 0.190 | 55% |
| `dc_bayes_v1_noshape` | 86 | 0.193 | 55% |
| `dc_mle_v0` | 96 | 0.195 | 57% |
| `elo_v0` | 96 | 0.189 | 57% |
| `multinomial_v1` | 96 | 0.191 | 57% |
| `ordered_logit_v1` | 96 | 0.194 | 56% |
| `random_forest_v1` | 96 | 0.188 | 57% |
| `stack_v1` | 96 | 0.190 | 57% |
| `xgboost_v1` | 96 | 0.190 | 57% |

Results so far: football_data_co_uk 96.
