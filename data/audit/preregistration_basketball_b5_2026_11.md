# Plan and pre-registration: basketball phase B5 (more leagues)

Written 14 Nov 2026, before any model was fitted on these leagues. Lang asked (third time)
for daily forecasts in ten more leagues and chose "Stay free ($0)". These rules decide what
goes live. They cannot change once a test-season result has been computed.

Claim labels: **[V]** Verified, with source. **[E]** Estimate, with basis. **[A]** Assumption.

## In plain words

Only three of the ten leagues have a free source that lists coming games: Spain (Liga ACB),
Italy (Lega Basket Serie A) and the Adriatic League (ABA). Each one is tested exactly like the
EuroLeague and the NBL in B1: same models, same settings grids, same checks, same pass rule.
A market goes live only if it passes. The other seven leagues are listed in
reports/basketball_more_leagues_2026_11.md with the reason and what would unlock them.

## 1. Data

| League | Source | Seasons | Tip-off |
|---|---|---|---|
| ACB | es.wikipedia "Temporada regular de la ACB" (2025/26 on) [V]; API-Basketball free plan for 2022/23 to 2024/25 [V: 306 regular-season games each] | 2022/23 to 2026/27 | date and time, Madrid time [A: the Canary Islands clubs' times are read as Madrid time too, which is the earlier reading, so a lock is never late] |
| LBA | it.wikipedia "Serie A 20xx-20yy (pallacanestro maschile)", calendar section [V] | 2022/23 to 2026/27 | date only |
| ABA | sr.wikipedia "Јадранска лига у кошарци 20xx/yy.", results by round [V] | 2022/23 to 2026/27 | round dates only (a game moved out of its round shows its own date) |

- Regular season only: ACB numbered rounds, LBA calendar, ABA round-robin phases (groups,
  Top 8, play-out). Play-offs, play-in and cups are left out.
- Club IDs: the club's es.wikipedia link (ACB) or data/manual/basketball_more_clubs.csv (plain
  names and the API's names). The build stops on an unknown name or a season with the wrong
  number of clubs.
- Left out of training and scoring: struck games (Trapani's 2025/26 games, voided when the
  club was excluded [V]) and any team score under 40 (forfeits).
- No second free source exists for these games, so there is no cross-check.
- Walk-forward unit: the game date (ABA: the round's first day, or the moved game's own date).

## 2. Models, grids, walk-forward rule

Exactly as B1 (data/audit/preregistration_basketball_b1_2026_10.md, sections 2, 3 and 5, with
Amendment 1): Elo for the winner and the margin line, the points model for the total and as the
challenger, the same naive benchmarks, the same grids. Each league gets its own settings.

## 3. Seasons

| League | Warm-up only | Tuning | Test |
|---|---|---|---|
| ACB | 2022/23 | 2023/24 | 2024/25 and 2025/26 |
| LBA | 2022/23 | 2023/24 | 2024/25 and 2025/26 |
| ABA | 2022/23 | 2023/24 | 2024/25 and 2025/26 |

One tuning season is short [E: about 180 to 306 games]; the grids are small (120 Elo and 25
points settings), so the risk of fitting noise is limited, and the test seasons judge it.

## 4. Checks and decision rule

The B1 checks W1, W2, H1, H2, T1, K1, K2 and L, with the same thresholds and the same 95%
paired bootstrap (4,000 resamples, game days as the unit, seed 2026). A market goes live in a
league only if its benchmark check and its calibration check pass:
winner W1 and K1; handicap H1 and K2 (margin); total points T1 and K2 (total).

Reported, not judged: accuracy, the favourite's win rate by how sure the model was (50-60%,
60-70%, 70-80%, 80-90%, 90%+), results by season, and for the ACB a cold-start check: the
daily run reads Wikipedia only (2025/26 on), so its ratings start a season later than the
test's. Reported: the mean difference in home-win chance between the two on 2026/27 games.

## 5. Live rules (if a market passes)

- Same daily run, ledger and lock window as B4: lock 24 to 48 hours before tip-off, never
  within 1 hour of it.
- LBA and ABA have no tip-off times. Their stand-in tip-off is 00:00 local time on the first
  day the game can be played (the listed date, or the round's first day), so every forecast
  locks at least a day before the real game. Flag: date_only.
- The ACB locks only games with a listed time.

## 6. Limits

- No odds: none are free (B0-D3), so no check against the bookmakers.
- The ACB's API-Basketball history is used for these tests only. It is cached on Lang's Mac,
  never committed and never read by the daily run.
