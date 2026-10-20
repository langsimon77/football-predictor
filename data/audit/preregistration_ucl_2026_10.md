# Pre-registration: Champions League goals model (20 Oct 2026)

Written before any Champions League forecast was made. Lang approved Champions League forecasts for the goals markets only (14 Oct 2026) and asked to continue on 20 Oct 2026.

## What runs

- Data (`fp.ingest.europe`): domestic league results from football-data.co.uk (11 main leagues, 8 results-only leagues) and UEFA club competition results from openfootball, 2016/17 onward, one club ID per club (`data/manual/uefa_club_aliases.csv`).
- Model (`fp.models.club_dc`): Dixon-Coles with club ratings around a league level per country, separate home advantage for domestic and European matches, none at a neutral ground; decay 0.002 per day, 1,100-day window, ridge 10 on clubs and 1 on league levels. These settings are fixed now and not tuned on Champions League results.
- Benchmarks: Champions League base rates (home, draw, away and over 2.5 frequencies of non-neutral Champions League matches in the previous 1,100 days), and an Elo rating fitted on the same matches with its own mapping from rating gap to home, draw, away (ordered logit refitted at each lock on matches before it). Reported only: the same Dixon-Coles fitted on European matches alone.
- Walk-forward: every Champions League match of 2021/22 to 2025/26 with a result (league or group stage and knockouts), predicted at its lock time (24 to 48 hours before kickoff) from results known by then. No market benchmark: no free source has Champions League odds.

## Checks (95% paired bootstrap intervals, 4,000 resamples, matches as the unit)

| Check | Rule |
|---|---|
| U1 | Home, draw, away RPS minus base rates: upper end below 0. |
| U2 | Home, draw, away RPS minus Elo: upper end below +0.002. |
| U3 | Over 2.5 goals log loss minus base rate: upper end below 0. |
| U4 | Every fit converges; top-pick accuracy of every forecast below 60% (leakage alarm). |

## What follows

- U1, U2 and U4 pass: home, draw, away and double chance are proposed for the background run (locked and scored daily, not published), then for the Model Lab on Lang's decision.
- U3 also passes: goal lines join them. If U3 fails, goal lines stay out. This split is fixed now, before the results.
- Any failure of U1, U2 or U4 means no proposal; a fix would be a new proposal with its own test.
