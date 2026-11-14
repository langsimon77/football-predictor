# Basketball: more leagues (phase B5), 14 Nov 2026

Lang asked for daily forecasts in ten more leagues, at $0 ("Stay free"). Rules:
data/audit/preregistration_basketball_b5_2026_11.md (committed before any fit).
Claim labels: **[V]** Verified, with source. **[E]** Estimate, with basis. **[A]** Assumption.

## In plain words

- Three new leagues are live from 14 Nov 2026: Spain (Liga ACB), Italy (Lega Basket Serie A)
  and the Adriatic League (ABA). With the EuroLeague and the NBL, five leagues in all.
- Each market was tested on two past seasons it never saw. Only markets that passed are shown.
- Seven leagues cannot be done for free: no free source lists their coming games. A paid data
  service would unlock six of them.

## 1. All twelve leagues

| League | Status | Markets shown | Why |
|---|---|---|---|
| EuroLeague | live since 30 Oct | winner, handicap, total points | B1 |
| NBL (Australia and New Zealand) | live since 30 Oct | winner | B1 (handicap and totals failed) |
| Liga ACB (Spain) | **live from 14 Nov** | winner, handicap | total points failed T1 |
| Lega Basket Serie A (Italy) | **live from 14 Nov** | handicap, total points | winner failed K1 (too cautious) |
| ABA League (Adriatic) | **live from 14 Nov** | handicap, total points | winner failed K1 (too cautious) |
| Turkish Super League | no free source | none | English and Turkish Wikipedia: results table only, no dates, no coming games [V] |
| Greek Basket League | no free source | none | Greek Wikipedia: results table only [V] |
| LNB Élite (France) | no free source | none | English Wikipedia: results table only; French: no game list [V] |
| Basketball Bundesliga (Germany) | no free source | none | English Wikipedia: results table only; German: no game list [V] |
| VTB United League | no source at all | none | no 2026/27 season page; API-Basketball lists only its cups [V] |
| CBA (China) | no free source | none | no game list on Chinese or English Wikipedia [V] |
| B.League (Japan) | no free source | none | no game list on Japanese or English Wikipedia [V] |

Official league sites were not used: the project reads only openly licensed sources (B0).

## 2. Test results (2024/25 and 2025/26, each forecast made before the game)

| | ACB | LBA | ABA |
|---|---|---|---|
| Test games | 612 | 448 | 466 |
| Favourite won (Elo) | 69.8% | 66.3% | 75.3% |
| Home-win-rate guess | 59.6% | 58.9% | 60.3% |
| W1 winner beats the guess (log loss, 95% range) | -0.095 (-0.130 to -0.058) pass | -0.083 (-0.110 to -0.054) pass | -0.188 (-0.223 to -0.151) pass |
| K1 calibration slope (0.8 to 1.2) | 0.96 pass | 1.27 **fail** | 1.44 **fail** |
| H1 margin beats the guess (CRPS) | -0.97 (-1.26 to -0.67) pass | -0.71 (-1.00 to -0.44) pass | -1.88 (-2.45 to -1.36) pass |
| K2 margin inside 90% range (86% to 94%) | 88.4% pass | 93.8% pass | 93.1% pass |
| T1 total beats the guess (CRPS) | -0.22 (-0.48 to +0.05) **fail** | -0.42 (-0.74 to -0.11) pass | -0.52 (-0.87 to -0.19) pass |
| K2 total inside 90% range | 88.9% | 87.7% pass | 90.3% pass |

Source: data/basketball/b5_results.json [V]. Settings: data/basketball/b5_settings.json.

**What "too cautious" means.** In Italy and the ABA, favourites won more often than the model
said: ABA favourites rated 80% to 90% won 93% of 84 games; those rated 90% or more won all 52.
The rule needs the slope between 0.8 and 1.2, so the winner stays hidden. The forecasts are
still locked in the ledger (flag winner_not_shown), so a fix can be tested on new games.

**How sure is sure (ACB, reported, not judged).** Favourite rated 50% to 60%: won 56% of 153
games. 60% to 70%: 66% of 145. 70% to 80%: 72% of 157. 80% to 90%: 82% of 122. 90%+: 94% of 35.
The chances match what happened, so a 75% pick wins about three times in four, not always.

## 3. How the daily run treats each league

- ACB: dates and Madrid times from Spanish Wikipedia; locks 24 to 48 hours before tip-off.
  Its Elo starts from data/basketball/b5_seed_ratings.json (ratings after 2024/25, computed by
  our own model from the test history), so the daily numbers equal the tested model's
  (largest difference 6e-10 on the 63 games of 2026/27 so far [V]). Without the seed they
  would differ by 6.7 points of chance on average, up to 27 [V].
- LBA: dates only, about one round ahead. Stand-in tip-off 00:00 Rome time on the game's date.
- ABA: round dates only (a game moved out of its round shows its own date). Stand-in tip-off
  00:00 Belgrade time on the round's first day. The page shows the round's dates.
- A pair listed twice at the same ground (the ACB 2026/27 page lists Burgos v Breogán twice
  and Breogán v Burgos never [V]) is not locked again until the page is fixed.

## 4. Options Lang did not ask for

1. **Paid data (about $15 a month [E: API-Basketball's entry plan]):** unlocks Turkey, Greece,
   France, Germany, China and Japan (it lists them, with odds for all but China [V]). Each
   would then go through the same test before going live.
2. **A winner fix for Italy and the ABA:** stretch the chances by the slope measured on the
   tuning season, and test it on the games locked from today (about 100 games, early 2027).
3. **EuroCup and the FIBA Champions League:** not checked yet [A: English Wikipedia may list
   their games the way it lists the EuroLeague's].
