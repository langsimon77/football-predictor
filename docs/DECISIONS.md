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
| 24 Sep 2026 | Phase 2 variant chosen on tuning seasons only: time-decay Bayesian Dixon-Coles with the shots-on-target layer (`bsot`). Tuning RPS 0.2014 (goals-only 0.2031, Elo 0.2016, fast DC 0.2022). Random-walk challenger on 2022/23: 0.2075 against 0.2063 for `bsot`, twice the cost, 2 of 35 EPL fits failed; not adopted (spec S5.1: keep whichever scores better). | Evidence in `reports/backtest_phase2_tune.md`. | Made |
| 24 Sep 2026 | Bayesian refits in the backtest are weekly; the fast model showed weekly and per-lock refits score the same (RPS 0.2022 both). | Keeps the backtest affordable without biasing it. | Made |
| 24 Sep 2026 | Bayesian parameterisation: centred first, non-centred retry with twice the draws. | La Liga defence spread is small, where centred sampling stalls; EPL attack is the opposite. Same model, same posterior. | Made |
| 24 Sep 2026 | Live Bayesian sampler: NumPyro. | Runner benchmark with the retry path: 7.1 s and 7.4 s against nutpie's 15.3 s and 11.9 s for the chosen model; all fits pass (`reports/sampler_benchmark.md`). | Made |
| 25 Sep 2026 | The previous session's scratch folder was cleared, losing the tuning-stage prediction files and the unfinished local test runs. The tuning report and this log survived, so the variant decision stands. Long backtests now run on GitHub Actions (`.github/workflows/backtest.yml`), one runner per league-season, with artifacts kept 90 days; downloads go to `data/interim/`. | Jobs must not depend on a laptop session. | Made |
| 25 Sep 2026 | Test stage run once on GitHub (run 36182318598, NumPyro): `bsot` RPS 0.1970 against Elo 0.1982 (interval of the difference −0.0030 to +0.0006), fast DC 0.1974, market 0.1912. Significant edge over Elo in the EPL only. | `reports/backtest_phase2_test.md`. | Made |
| 25 Sep 2026 | Finding: Dixon-Coles probabilities are too timid (calibration slope 1.22; Elo 1.00). Calibration map (spec S5.6) to be built in Phase 4 on regenerated tuning-season predictions (GitHub run 36183165274). | Explains Man City 64% against the market's 73%. | Made |
| 25 Sep 2026 | Corrected LEARN chapter 1F: the Bayesian model did not fix the shrinkage gap. | Honesty about an earlier prediction. | Made |
| 25 Sep 2026 | Phase 2 approved. `dc_bayes_v1` live as the primary model; `dc_mle_v0` and `elo_v0` continue as challengers. | Lang's answers 1 and 2. | Made |
| 25 Sep 2026 | The Bayesian model refits on every daily run, not only on lock days. | Spec S5.6 step 1; keeps the fallback posterior at most a day old. | Made |
| 25 Sep 2026 | Calibration moved forward to Phase 3a, before corners and cards. Applying it live needs a separate approval, since it changes model outputs. | Lang's answer 3. | Made |
| 25 Sep 2026 | Go-live verified on GitHub: dry run and real run pass; first Bayesian posteriors cached (3.6 MB). | Before the first lock on 8 Oct. | Made |
| 25 Sep 2026 | Decision rule for applying a correction: the whole 95% interval of the out-of-sample log-loss change must be below zero. | A negative average alone can be noise; the first script version recommended applying on the sign only, which was too weak. | Made |
| 25 Sep 2026 | Calibration not applied. Fixed map (Dirichlet, chosen on tuning seasons): test log loss −0.0003, interval −0.0027 to +0.0021. Monthly walk-forward power map: slope 1.24 to 1.09, log loss −0.0009, interval −0.0035 to +0.0017; BTTS +0.0009. Revisit in Phase 4. | `reports/calibration_phase3a.md`. The monthly result is a second look at the test seasons and is labelled as such. | Proposed, awaiting Lang |
| 25 Sep 2026 | Keep the 3,800 walk-forward Bayesian predictions in the repo (`data/backtests/`, 1.3 MB). | GitHub artifacts expire after 90 days; Phase 4 needs them. They are our own predictions, not third-party data. | Made |
