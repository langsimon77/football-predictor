# Decision Log

Append only. Newest at the bottom.

| Date | Decision | Reason | Status |
|---|---|---|---|
| 23 Sep 2026 | Project folder is `~/Downloads/football-predictor/`. No `git init` yet. | `~/Downloads` is not a Git repo. Repo visibility is Lang's call (PRD Q1). | Provisional |
| 23 Sep 2026 | Store the build prompt verbatim as `docs/SPEC.md`. | Every session and the PRD reference one fixed source. | Made |
| 23 Sep 2026 | No code until Lang approves the PRD. | Spec S0 and S15. | Made |
| 23 Sep 2026 | PRD approved by Lang. | Lang replied "Approved". | Made |
| 23 Sep 2026 | Q1: public GitHub repo. | Free standard-runner minutes on a faster runner; portfolio visibility. | Made |
| 23 Sep 2026 | Q2: add Phase 1F fast track (maximum-likelihood Dixon-Coles plus Elo, locking 1X2 and goals early). | Every gameweek without locked rows is lost evaluation data. | Made |
| 23 Sep 2026 | Q3: Lang answers the Question Queue by ticking checkboxes in the daily GitHub Issue. Dashboard Questions page is read-only. No write token in Streamlit. | A public app with a write token lets anyone write to the repo. | Made |
| 23 Sep 2026 | Q4: the daily run also publishes a static Fixtures page to GitHub Pages. | Streamlit Community Cloud cannot meet the 3-second mobile target from a cold start. | Made |
| 23 Sep 2026 | PRD fixes 5 to 26 adopted as written, including stacking on 1X2 only (Q23), "provisional" labels for unlocked matches, and scoring the newer row when a locked match moves more than 7 days (Q26). | Accepted with PRD approval. Lang can override any item. | Made |
| 23 Sep 2026 | Installed `uv` 0.12.18 to `~/.local/bin` with the official Astral installer. Ran `git init` locally on branch `main`. No commits yet. | Spec S2 requires `uv`. The Mac has no Homebrew. | Made |
| 23 Sep 2026 | Load football-data.co.uk from 2016/17 (PRD item 20), all four divisions. | Burn-in before tuning seasons; more promoted-team cases. | Made |
| 23 Sep 2026 | Do not use Understat, FPL, FBref, laliga.com, LaLiga Fantasy, or futbolfantasy.com as automated sources. | Understat robots.txt disallows all; FPL Terms 28(d) forbid automated extraction; FBref blocks bots; LaLiga terms bar reproduction; the rest reserve all rights. Spec S2. | Made |
| 23 Sep 2026 | Add openfootball `football.json` (CC0) as a source: fixture calendar and results fallback. | Full schedules with kickoff times, no API key, and a 100% match with football-data.co.uk on 2026/27 results. | Made |
| 23 Sep 2026 | Treat football-data.co.uk `Time` as Europe/London and store all times in UTC. | Cross-checked against openfootball local times. | Made |
| 23 Sep 2026 | Downloader retries timeouts and dropped connections (3 attempts, 10 s then 20 s waits). | A download from GitHub timed out on this connection. | Made |
| 23 Sep 2026 | D1 to D6 in `docs/DATA_SOURCES.md` section 5. | Consequences of the Phase 0 audit. | Approved 24 Sep 2026 |
| 24 Sep 2026 | Phase 0 approved. D1 to D6 adopted as proposed. | Lang replied "Approved". | Made |
| 24 Sep 2026 | GitHub repo: https://github.com/langsimon77/football-predictor (public). Commits use name "Lang" and email langdemijok@gmail.com, set for this repo only. | Lang's choice. The email will be visible in public commit history. | Made |
| 24 Sep 2026 | API-Football free plan cannot serve current-season data ("Free plans do not have access to this season, try from 2022 to 2024"). Team news runs through the Question Queue (D2 fallback). EPL Friday and Saturday referees stay unknown (D3). | Verified with Lang's key on 24 Sep 2026. | Made |
| 24 Sep 2026 | football-data.org still times out from this Mac on port 443. Test it from the GitHub runner in Phase 1. openfootball stays the primary calendar (D5). | Network path issue on this connection, not a key problem. | Made |
| 24 Sep 2026 | Installed GitHub CLI 2.101.0 to `~/.local/bin/gh`, SHA-256 checked against the official release checksums. | Lang chose this route for pushing. Lang signs in with `gh auth login`. | Made |
| 24 Sep 2026 | Daily run time 04:41 UTC (06:41 Juba). Lock = latest 04:41 run at or before kickoff minus 24 h. | PRD item 24: GitHub delays top-of-hour cron jobs. Every lock lands 24 to 48 h before kickoff (tested). | Made |
| 24 Sep 2026 | A result counts as known 3 hours after kickoff (`result_available_utc`). Matches with no known kickoff time wait 15 hours. | Conservative: later only costs information; earlier would leak. | Made |
| 24 Sep 2026 | Kickoff time source: football-data.co.uk `Time` (UK local) from 2019/20; openfootball local time before that. | Only the 2016/17 to 2018/19 files lack `Time`. openfootball covers them fully. | Made |
| 24 Sep 2026 | Odds at or below 1.0 are treated as missing and logged. | Source placeholder: Barcelona v Girona, 18 Oct 2025, Pinnacle closing O/U = 0.0. | Made |
| 24 Sep 2026 | UTC columns must be timezone-aware UTC; no silent coercion from naive times. | A test showed coercion would accept naive local times as UTC. | Made |
| 24 Sep 2026 | Ledger rows are SHA-256 hash-chained. CI fails if any old row changes or disappears. | Tamper evidence for the public record (spec S4). | Made |
| 24 Sep 2026 | `data/processed/` is git-ignored and rebuilt by `make data`. CI caches `data/raw/` between runs. | PRD item 25: keep third-party data out of the public repo. | Made |
| 24 Sep 2026 | User-Agent now names the repo URL as contact. | Wikimedia policy and good practice. | Made |
| 24 Sep 2026 | Pin `astral-sh/setup-uv@v10.2.0`. | That project publishes no floating `v10` tag; the first CI run failed on it. | Made |
| 24 Sep 2026 | football-data.org verified from GitHub's runner; 40 team spellings added from the API response. Daily run uses it on GitHub; local runs skip it. | Lang's home connection times out on that host. | Made |
| 24 Sep 2026 | Phase 1 approved. | Lang replied "approved". | Made |
| 24 Sep 2026 | Fast-track models live: `dc_mle_v0` (primary) and `elo_v0` (benchmark). | Phase 1F plan (PRD Q2). | Made |
| 24 Sep 2026 | Tuned settings: decay 0.002 per day, ridge 10, Elo K 10. The first grid's optimum sat on its edge, so the grid was widened and the choice repeated on tuning seasons only; test seasons were scored twice. Both runs recorded in `reports/backtest_1f.md`. | Transparency about the forking path. | Made |
| 24 Sep 2026 | Promoted-team prior estimated from 2017/18 to 2020/21 promoted clubs only: attack −0.21, defence +0.14. | Those seasons precede every tuning and test season, so no leakage. | Made |
| 24 Sep 2026 | Daily workflow live at 04:41 UTC. On days with nothing to lock it still commits, which keeps the scheduled workflow from being paused after 60 days. | Spec S10 keepalive. | Made |
| 24 Sep 2026 | First real daily run failed on `git add ledger` (folder did not exist yet); fixed, rerun succeeded. The failure opened issue #1 as designed; closed with a note. | Failure path exercised. | Made |
