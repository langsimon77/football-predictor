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
