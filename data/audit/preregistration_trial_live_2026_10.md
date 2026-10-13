# Pre-registration: Serie A and Ligue 1 background run, review for publishing

Written 13 Oct 2026, before the first background forecast was locked. Lang chose "Run what passed" on 13 Oct 2026: home, draw, away (with double chance) and yellow cards run in the background for Serie A and Ligue 1, locked and scored daily, not published. Goal lines, both teams score and corners stay off, because they failed the backtest (`reports/trial_backtest_2026_10.md`).

## What is judged

- The trial ledger (`ledger/trial/predictions.parquet`): the primary row `dc_bayes_v1` (home, draw, away with the goals fix; yellows from `cards_nb_v1`), the Elo row as benchmark, and league base rates computed at each lock from results known by then (last 1,100 days, as in the backtest).
- Results from `ledger/trial/results.parquet`. Yellows are judged only on matches with a full football-data.co.uk row.

## When

At the first weekly report after 300 matches are scored across the two leagues (about 16 rounds; my estimate is early January 2027 [E]). Then Lang decides. Until then nothing is published, whatever the early numbers say.

## Checks (95% paired bootstrap intervals, 4,000 resamples)

A live sample of 300 matches is small. These checks catch a clear breakage; they do not re-prove the backtest.

| Check | Rule | Basis |
|---|---|---|
| P1 | Home, draw, away RPS minus base rates: upper end below 0. | Backtest: −0.0304, interval half-width about 0.005 on 2,000 matches; about 0.013 on 300 [E]. |
| P2 | Home, draw, away RPS minus Elo: upper end below +0.005. | [A] "Not clearly worse than Elo" at this sample size. Backtest: −0.0005. |
| P3 | Yellows log score minus the league average: mean below 0. | [A] Backtest −0.0236; on 300 matches the interval would span about ±0.025 [E], so only the sign is asked. |
| P4 | Locks: every primary row locked 24 to 48 hours before kickoff, or flagged late, and no more than 2 trial-step failures in a row. | Same discipline as the live leagues. |

Reported, not judged: double chance hit rates by stated chance, the track-record percentages the Model Lab would show, and the goals fix numbers each month.

## What follows

- All four pass: I propose publishing these markets for Serie A and Ligue 1 (Model Lab Predictions, Pairs and slip checker). Lang decides.
- Any fails: no proposal. I report the numbers; any change is a new proposal with its own test.
