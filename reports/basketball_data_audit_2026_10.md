# Basketball data audit (phase B0)

Audit date: 24 Oct 2026. Auditor: Claude. Branch `basketball-b0`. Approved by Lang on 24 Oct 2026
("Approved: start phase B0, the data audit, as described").
Reproduce the counts with `uv run python basketball/audit_sample.py` (writes
`data/basketball/audit_sample.json`); parser tests in `tests/test_basketball_audit.py`.

Claim labels: **[V]** Verified, with source. **[E]** Estimate, with basis. **[A]** Assumption.
Nothing in this report is legal advice: the readings of terms of use are mine [E], made to
apply the project's rule (SPEC section 2): if a site's terms forbid the use, do not use it.

## 1. Summary for Lang

1. **The leagues' own data is closed to this project.** The NBA and the EuroLeague, the two
   leagues with the best free feeds, both forbid using their statistics in connection with any
   gambling activity, including legal gambling [V, section 2]. The Model Lab exists to help
   with bets, so their websites and feeds are out. Most of the other leagues sell their
   official data to bookmakers through Genius Sports [V, section 2].
2. **Openly licensed data covers three leagues now.** English Wikipedia (CC BY-SA 4.0) lists
   every EuroLeague and NBL game with its date, tip-off time and score, and every NBA game with
   its date and score (no time) [V, section 3]. That is enough for the team markets Lang chose:
   winner, handicap and total points come from a model of each team's points.
3. **No free odds history**, so at first the model can only be judged against a simple
   rating benchmark, not the bookmakers [V, section 4].
4. **No free box scores** (shots, rebounds, turnovers), so no pace or efficiency features from
   open data. EuroLeague and NBL games do have quarter scores [V, section 3].
5. **Recommendation:** B1 on the EuroLeague and the NBL first (dates and tip-off times, so the
   lock rule works as in football), then the NBA once Lang sets a lock rule for games without
   a tip-off time. The other seven leagues wait (section 6).

## 2. Terms of use (the deciding constraint)

| League | Official source and terms | Verdict |
|---|---|---|
| NBA | [V] nba.com/terms, last updated 13 Jul 2026, section 9: NBA statistics may be used only for news reporting or private, non-commercial purposes; never in connection with gambling (legal gambling included), fantasy or commercial products, or a regularly updated statistics database without consent. The terms cover the league's sites and apps, so also its data hosts. | **Do not use** NBA.com, its stats site or its data files. |
| NBA (Basketball-Reference) | [V] Bot policy (sports-reference.com/bot-traffic.html, via search): more than 20 requests a minute blocks a session; its data is licensed from third parties, which is why it offers no downloads. [V] Its data-use page returns HTTP 403 to automated reads, so its terms could not be read. | **Do not use** (terms unreadable; data licensed from the league's suppliers). |
| EuroLeague | [V] id.euroleague.net/terms (valid from 16 May 2025; covers euroleaguebasketball.net, its app and feeds): the same statistics clause as the NBA, gambling "including legal gambling activity" excluded. [V, 24 Oct 2026] Its API (api-live.euroleague.net) now declares an API key in its published specification but still answers without one; it has no robots.txt. | **Do not use** the API or website. |
| ACB (Liga Endesa) | [V] acb.com legal notice, section 3: downloading and storing for private use is allowed; any other reproduction needs ACB's prior written consent, except journalism that names the source. No clause on gambling or automated access. robots.txt allows all agents. [V, trade press] Genius Sports is ACB's exclusive official data partner, with stricter enforcement against unauthorised collectors. | **Not now.** Private use might be possible later, but our repository and Pages site are public. |
| LNB (Betclic Elite) | [V] lnb.fr has no robots.txt (the address returns the home page) and its terms page is drawn by script, so it could not be read automatically. | **Unknown; not used.** |
| BBL (Germany) | [V] easycredit-bbl.de Impressum: content is copyrighted; reproduction or publication needs prior written permission. No robots.txt. | **Not used.** |
| NBL (Australia) | [V] nbl.com.au: its legal page is a privacy policy with no clause on data use; robots.txt blocks only its tipping pages. [V, trade press] Genius Sports distributes official NBL data to sportsbooks. | **Website not needed:** Wikipedia covers the NBL (section 3). |
| ABA League | [V] aba-liga.com: robots.txt allows all; only a privacy policy PDF is linked; [V] aba-liga.com news: exclusive data partnership with Genius Sports since 2017. | **Not used** (no open dated results, section 3). |
| BSL (Turkey) | [V] tbf.org.tr answers HTTP 403 to our named User-Agent. | **Not used.** |
| GBL (Greece) | [V] esake.gr: no robots.txt and no legal page linked from the home page. | **Not used now** (see section 3). |
| CBA (China) | [V] cbaleague.com: the home page is script only; no robots.txt; no terms found. | **Not used.** |

## 3. Open sources: Wikipedia (CC BY-SA 4.0)

Read through the MediaWiki API with the project's named User-Agent, one request every 3 seconds,
every response cached (Wikimedia's User-Agent policy allows this; DATA_SOURCES.md section 1).
Counts from `data/basketball/audit_sample.json`, 24 Oct 2026.

### EuroLeague: "YYYY/YY EuroLeague regular season" articles

| Season | Games listed | With date | With tip-off time | Played |
|---|---|---|---|---|
| 2016/17 to 2018/19 | 240 each | all | all | all |
| 2019/20 | 306 | 306 | 306 | 252 (season stopped by COVID-19) |
| 2020/21 | 306 | 306 | 306 | 306 |
| 2021/22 | 278 | 278 | 278 | 278 (Russian clubs removed) |
| 2022/23, 2023/24 | 306 each | all | all | all |
| 2024/25 | 306 | 306 | 305 | 306 |
| 2025/26 | 380 | 380 | 380 | 380 |
| 2026/27 (now) | 80 | 80 | 80 | 70; the next round (10 games, to 28 Oct) already has times |

- [V] Times are CET or CEST, as each article states.
- [V] Cross-check, 2025/26: the 380 game boxes against the season's results grid: 378 home and
  away scores agree; 2 differ and must be resolved before training (the Europe pipeline's rule:
  a result the sources disagree on is left out).
- [V] Every game box also carries quarter scores and top scorers. Playoffs sit in separate
  articles (not counted here).
- [V] 2,854 played regular-season games over ten seasons (2016/17 to 2025/26).

### NBL: "YYYY/YY NBL season" articles

| Season | Games listed | With tip-off time | Played |
|---|---|---|---|
| 2016/17 | 138 | 119 | 114 |
| 2017/18 | 175 | 121 | 121 |
| 2018/19 to 2021/22 | 0 (no game list in the season article) | | |
| 2022/23, 2023/24 | 140 each | all | all |
| 2024/25 | 145 | 144 | 145 |
| 2025/26 | 166 | 166 | 166 |
| 2026/27 (now) | 165 | 59 | 41; 121 still to play, 18 of them with a time (to 8 Nov) |

- [V] The full 2026/27 schedule is listed; times are filled in about two weeks ahead.
- [A] The articles do not say which time zone their times use (probably the venue's local
  time). B1 must check this before any lock.
- [V] 867 played games with dates over seven seasons; the four missing seasons may sit in
  separate results articles (not checked).

### NBA: the 30 "YYYY/YY team season" articles (game logs)

| Season | Team logs | Regular-season games | Both teams' logs agree | Notes |
|---|---|---|---|---|
| 2025/26 | 30 of 30 | 1,227 played | 1,168 | 15 disagree (a wrong or reversed score in one log); 18 in one log only; 26 listed twice in a log (removed by game ID) |
| 2026/27 (now) | 30 of 30 | 28 played, 1,009 listed with IDs | 28 of 28 | the rest of the schedule is listed by date |
| 2016/17 | 29 with games | 2,700 rows | not checked | older logs use team-code IDs ("BOSPHI"), so the cross-check needs another key |

- [V] Logs give the date (no year: it follows from the season), home or away, and both scores.
  There are **no tip-off times**.
- [V] Each game is in two logs, so every result is checked twice; about 1.3% disagree, which
  is why the cross-check is needed.

### The other seven leagues

- [V] English Wikipedia has a results grid (scores, **no dates**) for the BBL, LNB, BSL and ABA
  League 2025/26 seasons; the ACB has one too. Without dates a model cannot follow form over a
  season or count rest days, so grids alone are not enough.
- [V, rough search] The Spanish ACB article (72 date and score pairs in 2025/26) and the Greek
  league article (110 pairs in 2024/25) have dated results in free text, not in a fixed
  template, so they need a custom reader. German, French, Turkish, Serbian, Croatian and
  Chinese articles showed no dated game lists.
- [V] The CBA has no English season article.

## 4. Odds (a market benchmark)

- [V] The Odds API: its v4 guide says the historical odds endpoints are for paid plans only.
- [V] The old Sportsbook Review NBA odds archive address returns HTTP 404; the Princeton
  historical odds database (NBA 2006 to 2023) is a university library resource.
- [E] Kaggle copies of NBA odds exist, but their licences and origins are unclear.
- So, at first, the benchmark is Elo (the rating model), as for the Champions League, which has
  no free odds either. Two ways to add the market later: Lang types Gal's basketball prices for
  the games he looks at (as the football value finder does), or a free current-odds feed is
  recorded every day from now on [A: The Odds API's free plan and terms for that are not yet
  checked].

## 5. What this means for B1 and B2

- [V] Open data gives dates, home or away, final scores, quarter scores (EuroLeague, NBL) and
  tip-off times (EuroLeague, NBL). From these: rest days and back-to-back games (all three),
  travel between cities (venues are on Wikipedia) [E].
- [V] Open data has no shots, rebounds, free throws or turnovers, so no possessions, pace or
  efficiency ratings. Total points can stand in for pace only roughly [E].
- Data depth: 2,854 EuroLeague and 867 NBL played games [V], and about 12,000 NBA
  regular-season games over ten seasons [E: 1,230 a season]. Elo and a points model need only scores and suit this; tree models get few
  extra features; LSTMs and Transformers are unlikely to have enough data outside the NBA.

## 6. Decisions for Lang

**B0-D1. Leagues to start with.** Proposal: the EuroLeague and the NBL in B1, the NBA after
B0-D2. The ACB and Greek league later only if a reader for their free-text results proves
reliable; the BBL, LNB, BSL, ABA League and CBA not now (no open dated results).

**B0-D2. A lock rule for NBA games, which have no tip-off time in open data.** Proposal: lock
each NBA game at the daily run on the day before its date. With the run starting between
about 05:00 and 07:30 UTC (as in football) and NBA tip-offs between about 16:00 UTC (noon in
New York) and 06:30 UTC the next morning (late games in the west), that is about 33 to 50
hours before tip-off [E]. That is slightly outside the 24 to 48 hour window for the latest
games, so Lang decides: accept up to 50 hours for the NBA, or skip the NBA.

**B0-D3. The benchmark.** Proposal: Elo only at first, plus Gal's prices when Lang types them.

**B0-D4. Official feeds.** Proposal: never use NBA or EuroLeague data (gambling clause); do not
use ACB or BBL content (reproduction needs consent). Revisit only if a league's terms change.

**B0-D5. Credit.** Wikipedia's licence asks for credit and for shared copies under the same
licence: the Model Lab cards and the repository credit Wikipedia, and any table built from it
and published carries CC BY-SA 4.0 [E].

## 7. Sources read (24 Oct 2026)

- NBA terms of use: https://www.nba.com/terms
- EuroLeague terms (EuroleagueID): https://id.euroleague.net/terms
- EuroLeague API specification: https://api-live.euroleague.net/swagger/v1/swagger.json
- Sports Reference bot policy: https://www.sports-reference.com/bot-traffic.html
- ACB legal notice: https://www.acb.com/es/liga/aviso-legal
- BBL Impressum: https://www.easycredit-bbl.de/impressum
- NBL legal page: https://www.nbl.com.au/pages/legal
- ABA League and Genius Sports: https://www.aba-liga.com/news/38440
- ACB and Genius Sports: https://www.sportbusiness.com/news/liga-acb-extends-data-partnership-with-genius-announces-tie-up-with-wsc-sports/
- NBL and Genius Sports: https://insidersport.com/2021/02/11/genius-sports-renews-long-running-nbl-data-distribution-deal/
- The Odds API v4 guide: https://the-odds-api.com/liveapi/guides/v4/
- Wikipedia, MediaWiki API: https://en.wikipedia.org/w/api.php (articles named in section 3)
