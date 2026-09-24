# PRD: EPL and La Liga Match Prediction System

| | |
|---|---|
| Owner | Lang |
| Build | Claude, lead statistician and engineer |
| Date | 23 Sep 2026 |
| Status | **Approved by Lang, 23 Sep 2026.** Answers to Q1 to Q4 and the adopted fixes are in `docs/DECISIONS.md`. |
| Spec | `docs/SPEC.md` holds the original build prompt, verbatim. "S5.6" means spec section 5.6. |

Claim labels: **[V]** Verified, with source. **[E]** Estimate, with basis. **[A]** Assumption.

## 1. Problem

A prediction record means something only if it provably predates kickoff and is scored against strong baselines. This project predicts every remaining 2026/27 EPL and La Liga match. It locks each prediction 24 to 48 hours before kickoff in an append-only ledger. It scores each one after the match against base rates, Elo, and the betting market. Git commit times prove every lock came before kickoff. The project is also Lang's course in applied Bayesian forecasting.

Markets per match: 1X2 and top scorelines. Goals: expected, O/U 1.5, 2.5, 3.5, both teams to score (BTTS). Corners: expected, O/U 8.5 to 11.5. Yellow cards: expected, O/U 3.5 to 5.5.

## 2. Success criteria

| # | Criterion | Measure |
|---|---|---|
| 1 | Beat league base rates and Elo on every market | Walk-forward backtest, 2023/24 to 2025/26. The paired bootstrap 95% interval on the score difference excludes zero. |
| 2 | Stay close to the market on 1X2 | RPS gap to de-margined closing odds, with a 95% interval. A gap under about 0.005 is a strong free-data result. [E, basis: published RPS comparisons of Dixon-Coles type models against closing odds. Confirm in Phase 4.] |
| 3 | Honest accuracy | 1X2 top-pick accuracy of 50 to 55% [E, S8]. Above 60% stops all work for a leakage hunt. |
| 4 | Calibration | Reliability diagram and ECE for every market and tier. Phase 4 sets pass thresholds from the backtest. |
| 5 | Ledger integrity | Every match from go-live locked 24 to 48 hours before kickoff. A CI test proves no locked row ever changed. |
| 6 | Reliable operations | Daily run under 45 minutes. Three consecutive clean runs. Forced-failure test passes. |
| 7 | Lang can explain every model | One `docs/LEARN.md` chapter per phase, each with a worked 2026/27 match. |

## 3. Scope

**In:** EPL and La Liga, next unplayed gameweek to season end. The four markets above. Append-only ledger. Daily, weekly, and monthly automation. Team news and the Question Queue. Seven-page Streamlit dashboard. The docs listed in S12.

**Out:** betting, staking, bookmaker accounts, paid data, paid APIs, paid LLM calls, in-play predictions, player props, other leagues (S14). Also out: post-stratification, raking, propensity matching, ARIMA (S5).

## 4. Constraints

- **Budget $0.** Free data, GitHub Actions, Streamlit Community Cloud, GitHub Pages.
- **Compute.** Public repos get free standard-runner minutes on 4 vCPU and 16 GB RAM. Private repos get 2,000 free minutes a month on 2 vCPU and 7 GB RAM. Jobs stop at 6 hours. [E, basis: GitHub docs as of mid 2026. Verify in Phase 0.] The daily run stays under 45 minutes. The backtest runs as a separate manual workflow, never inside the daily run.
- **Local machine.** Apple M1, 8 cores, 8 GB RAM, system Python 3.9. `uv` and `gh` are not installed. [V: checked on this Mac, 23 Sep 2026.] `uv` will install Python 3.12 for the project. 8 GB is enough for these models [E, basis: a few thousand matches and at most a few thousand parameters per fit].
- **Reproducibility.** Python 3.12, `uv.lock`, fixed seeds, commit hash on every prediction, `make rebuild`.
- **Scraping.** Check robots.txt and terms first. Cache every response. At most 1 request per 3 seconds per domain. Named User-Agent.
- **Connectivity.** Lang is in Juba on variable connectivity. Mobile first. Times shown in Africa/Juba, UTC+2 [V: IANA time zone database. South Sudan moved to UTC+2 in Feb 2021].
- **Leakage.** Every feature carries an `as_of` timestamp at or before lock time. Bookmaker odds are a benchmark only, never a feature.

## 5. Plan

Every phase ends at a gate: acceptance checks with results, a plain-English summary, a `LEARN.md` chapter, `DECISIONS.md` entries, and a `CHECKPOINT.md` update. Then I wait for "approved".

| Phase | Deliverable | Sessions [E] |
|---|---|---|
| 0 | Data audit, source decisions, team ID map | 1 to 2 |
| 1 | Pipeline, pandera checks, leakage guard, ledger | 2 to 3 |
| 1F (proposed, Q2) | Fast track: Elo plus maximum-likelihood Dixon-Coles, minimal daily workflow that locks 1X2 and goals | 1 |
| 2 | Bayesian Dixon-Coles, xG variant, promoted-team priors. Takes over from the 1F model in the ledger. | 3 to 4 |
| 3 | Corners and cards models | 2 to 3 |
| 4 | Challengers, stacking, calibration, tiers, full backtest against the market | 3 to 4 |
| 5 | Team news, impact model, Question Queue | 2 to 3 |
| 6 | Dashboard, plus a static fixtures page (Q4) | 3 to 4 |
| 7 | Full automation, deploy, failure tests | 1 to 2 |
| 8 | Live season learning loop | ongoing |

Total before Phase 8: about 18 to 26 sessions [E, basis: S11 estimates plus 1F].

## 6. Open questions

This section runs past one page. S0 asks me to list every problem I see before building. Each item gives the problem, the fix, and my recommendation.

### A. Decisions I need before Phase 0

1. **Repository.** `~/Downloads` is not a Git repo. I created `~/Downloads/football-predictor/` with docs only. Public or private GitHub repo? I recommend **public**: free runner minutes on a faster machine, and portfolio visibility. A private repo would spend up to about 1,500 of its 2,000 free minutes a month on the daily run [E: 45 minutes x 30 days, plus weekly, monthly, and CI runs]. `gh` is not installed. Either create an empty repo on github.com and send me the URL, or approve me to install `gh` and create it.
2. **Fast track (Phase 1F).** The season is under way. Every gameweek without locked rows is lost evaluation data (S11). Bayesian go-live needs Phases 0 to 2 plus a minimal Phase 7: about 7 to 10 sessions [E, S11]. A maximum-likelihood Dixon-Coles with time decay fits in seconds. It can lock 1X2 and goals rows after 4 to 6 sessions instead. It gets its own model version and stays in the ledger as a live challenger. **I recommend yes.**
3. **Question Queue answers.** S6 has dashboard buttons write to the repo with a token stored in Streamlit secrets. On a public app, anyone with the URL can press those buttons and write to your repo. Fix: you answer by ticking checkboxes in the daily GitHub Issue. That works from the email link and from the GitHub mobile app on a slow connection. The daily run reads only ticks made by your account. The dashboard Questions page shows the same questions, read-only. No write token leaves GitHub. **I recommend the Issue checkboxes.**
4. **Dashboard speed.** Streamlit Community Cloud puts apps to sleep after about 12 hours without visitors. Waking one takes a click and 30 seconds or more [E, basis: Streamlit docs as of mid 2026. Verify in Phase 0]. Even awake, Streamlit's first load on 4G usually takes several seconds [E]. The 3-second target (S2) will fail. Fix: the daily run also publishes a static Fixtures page to GitHub Pages. It is free, under 100 KB, and loads in about 1 second on 4G [E]. Streamlit keeps the interactive pages. **I recommend yes.**

### B. Errors in the spec, with fixes

5. **Double counting (S5.6.1).** Refitting on all data while using yesterday's posterior as today's prior counts every old match twice. Posteriors become too confident. Fix: refit on all data from fixed priors each day. Use yesterday's fit only to warm-start the sampler. That buys speed and adds no information.
6. **News as an ML feature (S5.5).** No free source keeps historical injury news. The ML models would train without the feature and predict with it. Fix: drop it from the ML features. Apply news as a capped multiplier on the final scoring rates (S6.3), the same way for every model.
7. **Leaky generated inputs (S5.3, S5.4, S5.5).** Goal supremacy, match closeness, and Dixon-Coles ratings feed other models as inputs. For past training matches, those inputs must be the values known before each match. Taking them from today's fit uses future results. Fix: save the walk-forward fits from the backtest and read inputs from those. Use as-of Elo supremacy where that is cheaper.
8. **EPL referee at lock time (S5.4).** The football-data.co.uk file lists matches only after they are played. Its `Referee` column trains the referee effect but never supplies the upcoming appointment. Fix: Phase 0 checks the site's upcoming fixtures file and football-data.org. Otherwise the referee goes to the Question Queue. La Liga has no referee history in the CSV, so the La Liga cards model starts without a referee effect.
9. **Unfair market comparison (S8).** Closing odds include confirmed lineups and late news. We lock 24 to 48 hours earlier. Fix: report two gaps. One against closing odds. One against the CSV's earlier odds, which I believe are snapshots taken a day or more before kickoff, not true opening odds [E, basis: football-data.co.uk notes.txt. Verify in Phase 0]. The second gap matches our information set more closely.
10. **Learning from tiny samples (S5.6.2, S5.6.3).** Over 60 matches, log-loss differences between decent models are mostly noise. Isotonic calibration on about 80 matches a month overfits. Fix: learn weights and calibration on the backtest pool plus live results, with time decay. The pool holds about 2,300 matches per market [E: 3 seasons x 2 leagues x 380]. Use beta calibration only until live data passes about 1,000 matches. Keep your 5% floor and 10-point weekly cap.
11. **Drift false alarms (S5.6.5).** There are more than 20 market and league pairs. Testing each weekly at 2 standard errors raises about one false alarm every two weeks [E: 2.3% one-sided per test]. Fix: a paired test against Elo on the same matches, which removes match-to-match noise, plus a Holm correction.
12. **Miss audit trigger (S5.6.4).** Red cards appear among the top misses nearly every week. "Same cause 3 gameweeks running" would fire on causes no model can foresee. "Model error or variance" cannot be judged from one match. Fix: auto-tag objective causes: red card, penalty, lineup differed from expected, referee. Propose fixes only for controllable causes that occur above their base rate. Judge model error in aggregate through calibration.
13. **Tier acceptance test (S7).** Any calibrated model shows separated hit rates when grouped by top-outcome probability. That is arithmetic, not evidence. The real question: do the data-quality flags pick out matches where the model does worse than its own probabilities promise? Fix: accept tiers on per-tier calibration plus the log-loss gap between flagged and unflagged matches.

### C. Infeasible or limited on free data

14. **No market benchmark for corners, cards, BTTS, O/U 1.5, or O/U 3.5.** The CSVs carry 1X2, O/U 2.5, and Asian handicap odds only [V: your header check, 23 Sep 2026, S3]. I know of no free, terms-compliant source of historical corner or card odds. So S8's test of corners and cards against the market cannot happen at $0. Fix: judge those markets against league base rates and a team-average model.
15. **xG source.** `HxG` and `AxG` exist only in the 2026/27 files. They may come from another provider and may include penalties. Training starts in 2021/22. Fix: use Understat non-penalty xG for every season. Treat `HxG` as a cross-check. Understat then carries the xG model, player importance, and rolling xG features: a single point of failure. If its terms forbid scraping, or it breaks, the fallback is a goals-only model.
16. **Player importance (S6.3).** Share of team npxG plus xA assumes the replacement produces nothing, so many adjustments will hit the 12% cap. Minutes share measures availability, not defensive quality. Fix: rebuild historical absences from Understat lineups (a regular starter who did not play). Estimate how much the replacement recovers. Set the cap from that data.
17. **Rest days (S5.5).** The football-data.org free tier likely covers the Champions League but not the Europa League, Conference League, or domestic cups [E, basis: football-data.org coverage page as of mid 2026. Verify in Phase 0]. The rest-day feature will be partial. I will document the gap.
18. **Manager history (S5.5).** Seeding five seasons of manager dates from my memory would be Assumption grade. Fix: pull them from Wikipedia through its public API. You confirm only new changes.
19. **La Liga team news.** I expect no compliant automated source [A, until Phase 0]. Most La Liga news will likely go through the Question Queue. Each question will carry a source link so it stays a 10-second answer.

### D. Smaller design changes

20. **Training window.** Starting at 2021/22 leaves no burn-in before the tuning seasons. It also gives only about 15 promoted teams per league for the promoted-team prior [E: 3 promoted a season x 5 seasons]. Fix: load from 2016/17, which is free. Add a no-crowd indicator for home advantage from June 2020 to May 2021. Time decay still down-weights old matches.
21. **Weighted likelihood (S5.1).** A time-decay weighted likelihood is not a true generative model, so its posterior intervals are approximate. Fix: Phase 2 checks interval coverage in the backtest. The random-walk challenger is the principled version. The S13 simulation test uses the unweighted model.
22. **Consistent numbers.** Stacked 1X2 will not match the Dixon-Coles scoreline heatmap. Fix: rescale the heatmap's home-win, draw, and away-win cells to the ensemble's 1X2. Every market on a page then agrees.
23. **Stacking scope.** Only 1X2 has several models. Other markets have one model plus baselines. Confirm stacking covers 1X2 only for now.
24. **Missed locks.** If a daily run fails or starts late, one 24-hour window of matches never gets locked. Fix: each run locks any unlocked match that kicks off within 48 hours. It flags any match locked with under 24 hours to go. Schedule cron off the hour, for example 04:41 UTC, because GitHub delays top-of-hour jobs [E].
25. **Repo size and data terms.** Daily commits of changing Parquet files bloat Git history. A public repo also republishes third-party data. Fix: commit the ledger and small dashboard files only. Keep raw snapshots in the Actions cache or in release assets, if each source's terms allow.
26. **Two clarifications.** (a) Should the dashboard show unlocked matches as "provisional"? I recommend yes. (b) When a locked match moves more than 7 days, I will score the new locked row and keep the original for the record. Agree?
