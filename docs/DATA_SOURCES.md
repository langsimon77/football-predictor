# Data Sources

Audit date: 23 Sep 2026. Auditor: Claude. Reproduce the file checks with `make audit` and `make test`.

Claim labels: **[V]** Verified, with source. **[E]** Estimate, with basis. **[A]** Assumption.

## 1. Summary

| Source | Status | Decision |
|---|---|---|
| football-data.co.uk season CSVs (`E0`, `SP1`, `E1`, `SP2`) | [V] Downloaded 44 files, 2016/17 to 2026/27. robots.txt allows general agents. | **Use.** Core match data and odds benchmark. |
| football-data.co.uk `fixtures.csv` | [V] Has a `Referee` column, filled for EPL, empty for La Liga. | **Use** for EPL referees on Sunday and Monday matches (section 4). |
| openfootball `football.json` | [V] Full 380-match schedules for 2016/17 to 2026/27. Public domain (CC0). Updated daily at 05:00 UTC. All 119 results so far in 2026/27 match football-data.co.uk exactly. | **Use** as the fixture calendar and results fallback. New source, not in the spec. |
| football-data.org API v4, free plan | [V] 12 free competitions, including Premier League, La Liga, and Champions League. 10 calls a minute. Free plan lists fixtures and tables only. No referees, cards, lineups, or past seasons. Source: football-data.org/coverage and /pricing. [V, 24 Sep 2026] Works from GitHub's runner with Lang's key: 380 PL, 380 PD, and 144 Champions League matches for 2026/27. Times out from Lang's home connection. | **Use** in the daily run (on GitHub) for Champions League dates and as a calendar cross-check. |
| Understat | [V] robots.txt is `User-agent: * Disallow: /`. Checked twice. | **Do not use.** Spec S2 forbids it. Section 5, D1. |
| Fantasy Premier League API | [V] FPL Terms 28(d): players "shall not use automated systems to access the Game and extract information from the Game". Terms 29: the Premier League owns all "Game data". | **Do not use.** Section 5, D2. |
| FBref | [V] Returns HTTP 403 to automated requests. The spec already bars current-season use. | **Do not use.** |
| laliga.com | [V] Legal notice clauses 3, 6, 10: content for personal, non-commercial use only; reproduction and public communication prohibited. robots.txt sets a 30-second crawl delay. | **Do not scrape.** |
| LaLiga Fantasy app API | [V] Terms are silent on automation, but the endpoints are unofficial and the parent laliga.com terms bar reproduction. | **Do not use.** Grey area. Lang may overrule. |
| futbolfantasy.com (Spanish injury lists) | [V] robots.txt allows all. Legal notice reserves all exploitation rights and is silent on scraping. | **Do not scrape.** Link to it in questions so Lang can read it by hand. |
| rfef.es (La Liga referee appointments) | [V] robots.txt allows crawling. Legal notice only bars copying audiovisual content. Appointments go up the day before each match, before 16:00 Spanish time (RFEF notice, Aug 2025). | Compliant, but always **too late for our lock**. Section 5, D3. |
| API-Football free plan (api-sports.io) | [V, 24 Sep 2026, Lang's key] 100 requests a day, 10 a minute. The API answers: "Free plans do not have access to this season, try from 2022 to 2024." [V, 26 Sep 2026] The terms pages (api-football.com/terms, api-sports.io/terms) sit behind a bot check, so their rules on storing data could not be read automatically. | **Not usable for live data.** Its 2022 to 2024 injury history could calibrate the missing-starter effect only once Lang confirms the terms allow it. |
| Wikipedia API | [V] Allowed with a descriptive User-Agent that includes contact details (Wikimedia User-Agent policy). Content is CC BY-SA, so we attribute it. [V, 26 Sep 2026] The club infobox gives the current manager for all 40 clubs of 2026/27 (`data/manual/wikipedia_titles.csv`). | **Use** for manager changes (Phase 5): clubs playing in the next 72 hours, once a day. Attributed in `data/manual/managers.csv`. |

### Platforms

| Platform | Finding |
|---|---|
| GitHub Actions, public repo | [V] Standard Linux runner: 4 CPU, 16 GB RAM, 14 GB SSD. "Free and unlimited on public repositories." Private repos get 2 CPU and 8 GB. Jobs stop after 6 hours. Cache limit 10 GB per repo. Source: docs.github.com runner and limits pages. |
| Scheduled workflows | [V] "In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days." The docs do not define activity. Plan: daily data commits, plus a monthly `gh workflow enable` step as insurance. |
| Streamlit Community Cloud | [V] "All apps without traffic for 12 hours go to sleep." Waking takes a visitor click. Limits: up to 2 cores, 2.7 GB RAM. Source: docs.streamlit.io. Confirms PRD Q4. |
| GitHub Pages | [E, basis: long-standing free hosting for public repos] Check at deploy in Phase 6. |

## 2. football-data.co.uk in detail

**Coverage** [V: `make audit`, 23 Sep 2026]

| Item | EPL (`E0`) | La Liga (`SP1`) |
|---|---|---|
| Matches, 2016/17 to 2025/26 | 3,800 | 3,800 |
| Matches in 2026/27 so far | 50 (5 rounds) | 69 (7 rounds, one postponed) |
| Shots, shots on target, fouls, corners, cards | 100% every season | 100% every season |
| `Referee` | 100% every season | Column absent |
| `HxG`, `AxG` | 2026/27 only, 100% | 2026/27 only, 100% |
| `Time` (kickoff) | From 2019/20 | From 2019/20 |
| Closing odds (`...C...` columns) | From 2019/20 | From 2019/20 |
| Pinnacle closing (`PSCH`) | Until 8 Jan 2026, then gone | Same |
| Betfair Exchange closing (`BFECH`) | From 2024/25, 94 to 100% | From 2024/25, 92 to 100% |
| Market-average closing margin | 3.9 to 4.2% until 2024/25, then 5.7 to 5.9% | 4.3 to 4.8%, then 6.1% |
| Betfair Exchange closing margin | 0.6% | 0.5% |

Second tiers (`E1`, `SP2`) have the same columns. `SP2` 2016/17 has no match statistics.

**Facts that shape the models**

1. **Kickoff times are UK local time** [V]. La Liga kickoffs at 21:00 Spanish time show as 20:00. The first 2026/27 matches in openfootball (local times) differ by exactly one hour for La Liga and zero for the EPL. The pipeline converts `Time` from Europe/London to UTC.
2. **Pre-closing odds are not opening odds** [V: notes.txt]. "Betting odds for weekend games are collected Friday afternoons, and on Tuesday afternoons for midweek games." For a Saturday match that is about 24 hours before kickoff, close to our lock. Confirms PRD item 9.
3. **Yellow cards are counted differently by league** [V: notes.txt]. English yellow counts leave out the first yellow of a two-yellow sending off. European leagues, including La Liga, count it as a yellow plus a red. The cards model already has a league intercept, which absorbs this. Averages over 2023/24 to 2025/26: EPL 3.99 yellows a match, La Liga 4.55.
4. **No corners, cards, BTTS, O/U 1.5, or O/U 3.5 odds** [V: column list]. Confirms PRD item 14.
5. **Match statistics come from BBC, Flashscore, and ESPN** [V: notes.txt]. The `HxG` provider is not documented [A: unknown provider and penalty treatment].

**robots.txt note** [V]. The file allows all general agents and blocks named AI crawlers, including GPTBot, ClaudeBot, Claude-Web, and Anthropic-AI, under the heading "Block major AI training models". Our pipeline is Lang's own downloader. It identifies itself as `football-predictor/0.1`, fetches only the published CSV files, and caches them. It does no AI training. I read this as permitted. I flag it so Lang can judge.

## 3. Freshness

- [V] The EPL file now runs to 20 Sep 2026. The 31 Aug stop seen on 23 Sep morning was a lag, now cleared. The site header says "Updated: 22/09/26".
- [V] Both leagues are on the combined September and October international break. openfootball shows La Liga resuming Fri 9 Oct (Málaga v Espanyol, 21:00 Spanish time) and the EPL on Sat 10 Oct (Arsenal v Leeds, 12:30 UK time).
- [V] Levante v Athletic Club (La Liga matchday 6) is postponed to 21 Oct.
- [V] 290 of 311 remaining La Liga fixtures have no confirmed kickoff time yet. La Liga sets times a few weeks ahead. Every remaining EPL fixture has a time.
- [V] `fixtures.csv` still lists the 18 to 20 Sep round. The site refreshes it on Friday and Tuesday afternoons.

**Freshness rule for Phase 1:** compare each source's latest result with the openfootball calendar. If football-data.co.uk is more than 72 hours behind, take results from openfootball and flag the run. openfootball has scores only, not statistics, so corners and cards wait for football-data.co.uk.

## 4. Team ID mapping

- `data/manual/teams.csv`: 67 clubs (35 English, 32 Spanish) that played in the top flight from 2016/17 to 2026/27.
- `data/manual/team_aliases.csv`: 198 spellings from three sources: football-data.co.uk (67), openfootball (91), and football-data.org (40, current season, added 24 Sep 2026 from the runner).
- `tests/test_team_mapping.py`: 72 tests, all passing [V: 23 Sep 2026]. They prove:
  - every top-flight name in every season maps, giving exactly 20 clubs;
  - every newly promoted club, 3 per season, appears under the same name in the previous season's second tier, so promoted-team priors join the right history;
  - both sources name the same 20 clubs in each of the 22 league-seasons;
  - all 119 matches played so far in 2026/27 have the same date and score in both sources.
- football-data.org spellings came from the API itself, not from memory. A test maps them wherever the API is reachable (CI).

## 5. Consequences for the spec: decisions for Lang

**D1. No compliant historical xG.** Understat is barred. `HxG` exists only in 2026/27. So the xG variant of the goals model (S5.1) cannot be backtested on 2023/24 to 2025/26, and ML challengers cannot use rolling xG in training.
Proposal: use **shots on target** as the second, noisier observation of team strength in the backtested model, since it exists for every season. Add `HxG` as a live challenger that must earn its ensemble weight on 2026/27 data. ML challengers use shots and shots on target.

**D2. No compliant automated team news.** FPL and Understat are barred, and no La Liga source passed. Player importance (S6.3) has no player data either.
Proposal: Lang registers a free API-Football key. In Phase 1 I verify its terms and whether the free plan covers 2026/27 injuries, referees, and player stats. If it does, news is automated for both leagues. If it does not, news runs through the Question Queue with one question per match. For each team the checkboxes ask: how many regular starters are out (0, 1, 2, 3 or more), and is the main goal threat out? Each question links to a team-news page. The adjustment uses a fixed effect per missing starter, labelled as an Assumption, since we have no player data. S6.5 still tests whether news helps.

**D3. Referees at lock time.**
- EPL: the history is complete. Upcoming appointments reach `fixtures.csv` on Friday afternoon. That is in time for Sunday and Monday matches, but not Friday or Saturday ones.
- La Liga: appointments are published the day before kickoff, after our lock. The La Liga referee is never known at lock time.

Proposal: the La Liga cards model has no referee effect, and "unknown referee" is not a quality flag for La Liga, because every match is the same and the backtest reflects that. For EPL Friday and Saturday matches, the referee is unknown unless API-Football supplies it. No referee questions, to keep your question load down.

**D4. Market benchmark.** Pinnacle closing odds ended on 8 Jan 2026.
Proposal: the primary benchmark is Pinnacle closing where present, else Betfair Exchange closing. Secondary: market-average closing, which covers every season. The fair-timing comparison uses the Friday or Tuesday pre-closing snapshot. The same rules apply to O/U 2.5.

**D5. Fixture calendar.** Proposal: openfootball is the primary calendar, and football-data.org is a cross-check plus the Champions League dates, once Lang has a key. A match without a confirmed kickoff time cannot be locked. The daily run reports any match within 72 hours that still has no time.

**D6. First lock deadline.** La Liga's Fri 9 Oct match kicks off at 19:00 UTC. The 05:00 UTC run on Thu 8 Oct must lock it. Phase 1 and Phase 1F must be running on GitHub Actions, with one dry run, by Wed 7 Oct. That needs the public repo.
