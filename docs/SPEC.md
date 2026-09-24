<!-- Original build prompt from Lang, received 23 Sep 2026, stored verbatim below the line. PRD section references like "S5.6" point here. Changes to the spec go through docs/DECISIONS.md, not edits to this file. -->

---

# Build Prompt: EPL and La Liga Match Prediction System

Paste everything below the line into Claude Code, run from an empty folder that is a Git repository linked to GitHub.

---

## 0. Role, owner, and how to work with me

You are the lead statistician and engineer on a personal learning and portfolio project. The owner is Lang, a petroleum engineer with strong quantitative instincts and beginner-level Python. You write all the code. Lang runs it, reads your explanations, and approves each phase.

Rules of engagement:

- **PRD first.** Before writing any code, produce a one-page PRD (Problem, Success criteria, Scope, Constraints, Plan, Open questions) based on this prompt. Wait until Lang types "approved" or "build it". A question from Lang is not approval.
- **Phase gates.** Work in the phases in Section 11. At the end of each phase, show the acceptance checks, their results, and a plain-English summary. Wait for "approved" before starting the next phase.
- **Teach as you build.** After each phase, add a chapter to `docs/LEARN.md` explaining the method in plain English, with one worked example on a real 2026/27 match. Show the maths once, then the intuition. Lang should be able to explain every model to someone else.
- **Label every claim.** In docs and in the dashboard, mark statements as Verified (with source), Estimate (with basis), or Assumption.
- **Writing style for all docs and dashboard text:** short sentences, active voice, no em dashes or en dashes, no filler. Add a CI check that fails if the characters U+2014 (em dash) or U+2013 (en dash) appear in any `.md`, `.py` string, or dashboard text.
- **Push back.** If something in this prompt is wrong, infeasible on free data, or will leak future information into training, say so before building it, give the reason, and propose the fix.
- **Never self-modify silently.** The system updates its parameters and ensemble weights automatically. Any change to model structure, features, or code is proposed in `docs/MODEL_CHANGELOG.md` and waits for Lang's approval.
- **Keep a decision log.** Append every decision, its reason, and its date to `docs/DECISIONS.md`. At the end of each session, write a checkpoint to `docs/CHECKPOINT.md`: decisions made, open questions, next actions with owners, facts still unverified.

## 1. Objective

Build an automated system that, for every English Premier League (EPL) and Spanish La Liga match from the next unplayed gameweek until the end of the 2026/27 season, predicts:

1. **Match result:** probabilities for home win, draw, away win (1X2), plus the most likely scorelines.
2. **Goals:** expected goals per team and total; probabilities for over/under 1.5, 2.5, 3.5; both teams to score.
3. **Corners:** expected corners per team and total; probabilities for over/under 8.5, 9.5, 10.5, 11.5.
4. **Yellow cards:** expected total yellow cards (HY + AY); probabilities for over/under 3.5, 4.5, 5.5.

Predictions are generated and **locked 24 to 48 hours before kickoff**, published to an interactive dashboard, scored after the match, and fed back into the models.

Purpose: learning and portfolio. The yardstick is proper scoring rules and calibration against strong baselines, including the bookmaker market. There is no betting layer, no staking, and no money in scope.

## 2. Hard constraints

- **Budget: $0.** Free data sources, free compute, free hosting only. Do not add any paid API, paid LLM call, or paid hosting. If a free source fails, fall back to the next free source or to the Question Queue (Section 6).
- **Compute:** GitHub Actions free runners (verify current specs and the 6-hour job limit in Phase 0). The full daily run must finish in under 45 minutes.
- **Hosting:** Streamlit Community Cloud for the dashboard. GitHub repository holds code, data, and the prediction ledger.
- **Language:** Python 3.12. Pin all dependency versions in `pyproject.toml` with a lock file (use `uv`).
- **Reproducibility:** fixed random seeds, recorded model version (Git commit hash) on every prediction, and a single command that rebuilds everything from raw data: `make rebuild`.
- **Legal and polite scraping:** check each site's robots.txt and terms before scraping. Cache every response. Rate-limit to at most 1 request every 3 seconds per domain. Identify the scraper with a clear User-Agent. If a site's terms forbid automated access, do not scrape it; log it and use the Question Queue instead.
- **Connectivity:** Lang is in Juba, South Sudan, on variable connectivity. The dashboard must load fast on mobile (target under 3 seconds on a 4G connection) and work on a phone screen.

## 3. Data sources

Verify every source in Phase 0 before relying on it. Record what you verified, and when, in `docs/DATA_SOURCES.md`.

| Source | What it provides | Status as of 23 Sep 2026 | Use |
|---|---|---|---|
| [football-data.co.uk](https://www.football-data.co.uk/data.php) CSVs (`E0`, `SP1`, plus `E1`, `SP2` for promoted-team priors) | Results, half-time scores, shots, shots on target, fouls, corners (HC, AC), yellow cards (HY, AY), red cards, opening and closing odds from several bookmakers, over/under 2.5 odds, Asian handicap odds. The 2026/27 files now include `HxG` and `AxG` columns. | Verified: column headers checked on 23 Sep 2026. EPL file has a `Referee` column. La Liga (`SP1`) file has **no** `Referee` column. [Column notes](https://www.football-data.co.uk/notes.txt) | Core historical and current match data. Closing odds used as a **benchmark only**, never as a model feature. |
| [football-data.org](https://www.football-data.org/coverage) API v4, free tier | Fixtures, kickoff times, results, standings. The free tier covers the Premier League and Primera Division. Match resource can include referees. | Verified: PL and PD are in the free tier. Unverified: free-tier rate limit and whether referees are returned on the free tier. Check in Phase 0. [Match docs](https://docs.football-data.org/general/v4/match.html) | Fixture calendar, kickoff times, rest days (including Champions League, Europa League, and cup fixtures where free), La Liga referee if available. Fallback source for results when the CSV lags. |
| [Understat](https://understat.com/league/EPL) | Match-level and shot-level xG, player xG and xA, minutes. Covers EPL and La Liga back to 2014/15. | Verified: 2026/27 EPL season page is live. Scraping is required (for example the `understatapi` package). | Player importance weights for injury adjustments. Cross-check of the `HxG`/`AxG` columns. |
| [Fantasy Premier League API](https://fantasy.premierleague.com/api/bootstrap-static/) (unofficial, public) | Player status, injury and suspension news text, `chance_of_playing_next_round`, team lists. | Widely used and documented by the community. Unofficial, so it can change without notice. | EPL team news, automated. |
| La Liga team news | No free official structured feed. | Unverified. Candidates to evaluate in Phase 0: the official LaLiga Fantasy app endpoints, public injury pages on Spanish fantasy sites, club press releases via RSS. Check terms for each. | La Liga team news. If no compliant source works, rely on the Question Queue. |
| FBref | Historical basic stats only. | Verified: FBref lost its Opta licence in January 2026 and no longer updates advanced stats. [Source](https://www.liamhenshaw.com/writing/where-to-find-football-data) | Do not use for current-season features. |

Data window: seasons 2021/22 through 2025/26 for training, plus 2026/27 to date. Time-decay weighting (Section 5.1) handles the fact that older matches matter less.

Data freshness check: on 23 Sep 2026 the football-data.co.uk EPL file appeared to stop at 31 Aug 2026 while the La Liga file ran to 20 Sep 2026. This may be an update lag or a fetch artifact. Unverified. Build a freshness check that compares each source's latest result with the fixture calendar and switches to the fallback source when a source is more than 72 hours behind.

Team name mapping: build and unit-test one canonical team ID table that maps every source's spelling (for example "Man United", "Manchester United FC", "Manchester Utd").

## 4. Data pipeline and storage

- Layout: `data/raw/` (immutable downloads, dated), `data/interim/`, `data/processed/` (Parquet), and one DuckDB file for queries.
- Validate every table with `pandera` schemas: no duplicate matches, goals and counts non-negative, kickoff times in UTC, every team mapped.
- **Leakage guard.** Every feature for a match must use only information available before that match's prediction lock time. Build features with an explicit `as_of` timestamp. Write a unit test that fails if any feature row uses data timestamped after its `as_of`.
- **Prediction ledger.** `ledger/predictions.parquet` is append-only. Each row: match ID, league, kickoff, lock timestamp, model version (commit hash), every predicted probability and expected count, confidence tier, news adjustments applied, and unanswered questions. Never edit or delete a locked row. Outcomes and scores go in a separate `ledger/results.parquet` joined on match ID.

## 5. Modelling stack

This is the locked method set. Do not add Multilevel Regression with Post-stratification (the post-stratification step), Iterative Proportional Fitting (raking), Propensity Score Matching, or ARIMA. Reasons, for `docs/LEARN.md`: football has no target population to post-stratify or rake to; propensity matching answers causal questions, not prediction questions; one team's 38-match season is too short and noisy for ARIMA, and exponential time decay does the same job better.

### 5.1 Goals and match result: Bayesian hierarchical Dixon-Coles model (primary model)

- Fit in PyMC with a fast NUTS sampler (nutpie or NumPyro backend). Choose the faster one on the GitHub runner in Phase 2 and record the benchmark.
- Structure:
  - Home goals ~ Poisson(λ_home), away goals ~ Poisson(λ_away).
  - log λ_home = μ_league + home_adv_league + attack_home + defence_away
  - log λ_away = μ_league + attack_away + defence_home
  - Dixon-Coles low-score correction term ρ for 0-0, 1-0, 0-1, 1-1.
  - **Multilevel (hierarchical) priors:** team attack and defence effects drawn from league-level distributions, so teams with little data are pulled toward the league average. This is the "multilevel regression" part of MRP, kept because it works.
  - **Promoted teams:** prior mean shifted using their previous season in `E1` or `SP2`, scaled by the historical gap between promoted teams' second-tier and first-tier ratings.
  - **Time dynamics:** exponential time-decay weights on the likelihood, weight = exp(−ξ × days since match). Tune ξ by walk-forward validation. As a challenger, fit a Gaussian random-walk version where team strengths evolve by gameweek. Keep whichever scores better.
  - **xG signal:** add non-penalty xG as a second, noisier observation of the same underlying team strengths (a joint model of goals and xG), or use an xG-blended target. Test both and keep the better one.
- Outputs: the full posterior of the scoreline matrix (0 to 10 goals each side). Derive 1X2, over/under, both teams to score, and top scorelines from it. Keep posterior draws so each probability carries an uncertainty interval.
- Diagnostics required on every fit: R-hat below 1.01, bulk ESS above 400, zero divergences. If a fit fails diagnostics, do not publish from it. Fall back to the previous day's posterior and flag the run.

### 5.2 Match result challengers

- **Ordered logistic regression** on the rating difference (home, draw, away treated as ordered outcomes). This is the correct version of "log-odds for win or lose": football has three outcomes and about a quarter of matches are draws, so binary logistic regression is wrong here.
- **Multinomial logistic regression** with regularisation on the full feature set.
- **XGBoost** and **Random Forest** multiclass classifiers on the feature set in Section 5.5. Tune with time-series cross-validation only, never random K-fold.
- **Elo baseline** (goal-difference adjusted) as a sanity benchmark.

### 5.3 Corners: hierarchical negative binomial GLM

- Corners per team per match ~ NegativeBinomial(mean, dispersion).
- log mean = league intercept + home effect + team corners-for effect + opponent corners-against effect + β × expected goal supremacy from the goals model + β × rolling shot volume.
- Team effects partially pooled within league. Time-decay weights as in 5.1.
- Test Poisson versus negative binomial and report the dispersion estimate. Keep negative binomial unless the data shows no overdispersion.
- Total corners distribution: simulate from the two team distributions (posterior predictive), so over/under probabilities include parameter uncertainty.

### 5.4 Yellow cards: hierarchical negative binomial GLM with referee effect

- Target: total yellow cards in the match (HY + AY). Document how a second yellow is counted in the source data.
- log mean = league intercept + referee random effect + home and away team discipline effects + β × expected match closeness (from the goals model) + β × rolling fouls + derby flag + fixture importance (relegation or title race, late season).
- Referee effect partially pooled so new referees start near the league average.
- Referee data: EPL from the football-data.co.uk `Referee` column. La Liga from football-data.org if the free tier returns it, otherwise from a compliant public source, otherwise the Question Queue. If the referee is unknown at lock time, integrate over the referee distribution and lower the confidence tier.

### 5.5 Features for the machine learning challengers

All computed with the `as_of` rule:

- Dixon-Coles posterior means and standard deviations for both teams.
- Elo ratings.
- Rolling (exponentially weighted) xG for and against, shots, shots on target, corners, fouls, cards.
- Rest days and fixture congestion, including European and cup matches where the free data allows.
- Home and away splits.
- Manager tenure (days since appointment). Maintain `data/manual/managers.csv`, seeded by you and confirmed by Lang through the Question Queue.
- Team news adjustment (Section 6).
- Promoted-team flag and matches played this season.

Never use bookmaker odds as a feature. They are the benchmark only.

### 5.6 Ensemble, calibration, and "learning from failures"

This is the adaptive layer. It must be rigorous and bounded.

1. **Daily Bayesian updating.** Each run refits the Bayesian models on all data to date. Yesterday's posterior informs today's fit. This is how new results move team ratings.
2. **Weekly stacking re-weight.** For each market, combine the models with weights learned from their exponentially weighted log loss on recent locked predictions (use a hedge or multiplicative-weights rule, or Bayesian stacking with `arviz`). Guardrails:
   - Minimum 60 scored predictions per market before weights move off the Phase 4 backtest weights.
   - Each model keeps a floor weight of 5% so it can recover.
   - Weights move at most 10 percentage points per week.
   - Every weight change is logged with the evidence behind it.
3. **Monthly calibration check.** Fit a calibration map (beta calibration or isotonic, whichever validates better) on locked predictions. Apply it only if it improves out-of-sample log loss on a held-out slice. Log the decision.
4. **Post-match miss audit.** After each gameweek, rank predictions by surprise (−log p of the actual outcome). For the 5 biggest misses per league, record a tagged cause: red card, penalty, late team news missed, referee effect, model error, or variance. Show this on the dashboard. If one cause repeats for 3 gameweeks in a row, draft a proposed fix in `docs/MODEL_CHANGELOG.md` for Lang's approval.
5. **Drift monitor.** Track rolling 4-gameweek performance per market against the backtest baseline. If performance drops more than 2 standard errors below baseline, flag it on the dashboard and open a GitHub Issue.

The system learns by updating parameters and weights. It does not rewrite its own code.

## 6. Team news and the Question Queue

Lang chose automated news scraping with himself as the fallback. Build it this way:

1. **Collect.** Every daily run, pull news for all matches kicking off in the next 72 hours. EPL: FPL API player status, news text, and `chance_of_playing_next_round`. La Liga: the compliant source chosen in Phase 0.
2. **Parse without paid AI.** Use rule-based parsing: fuzzy-match player names to squad lists, classify status (out, doubtful, suspended, available) from the source's structured fields or from keyword rules in English and Spanish. Log parse confidence.
3. **Quantify impact.** Player importance = the player's share of team non-penalty xG plus xA (for attackers) or share of minutes in a defensive role (for defenders and goalkeepers), from Understat over the last 1,500 to 2,000 minutes. Expected missing contribution = importance × probability of absence. Convert to a bounded adjustment on the team's attack or defence rate. **Cap any single match adjustment at ±12% of the rate.** Record the adjustment in the ledger.
4. **Ask Lang when the scraper fails.** Generate a question when any of these is true: a source failed; a parse is low confidence; a key player (top 3 by importance) has unknown status; the La Liga referee is unknown; a manager change is suspected. Rules for questions:
   - Specific and answerable in under 10 seconds. Example: "Real Betis vs Sevilla, Sat 26 Sep, 20:00 UTC: Is Isco (22% of Betis xG+xA) available? Options: Available / Doubtful / Out / Don't know."
   - Maximum 10 questions per day, ranked by how much the answer would change the prediction (expected shift in 1X2 probabilities).
   - Delivery: open one GitHub Issue per day titled "Questions for Lang: <date>" so Lang gets an email, and show the same questions on a "Questions" page in the dashboard with one-tap answer buttons.
   - The dashboard writes answers to `data/manual/answers.yaml` through the GitHub API, using a fine-grained personal access token scoped to this one repository with contents write only, stored in Streamlit secrets.
   - Deadline: answers received before the lock run are used. Unanswered questions default to "Don't know", the prediction proceeds without that adjustment, and the confidence tier drops one level. The ledger records which questions were unanswered.
5. **Measure whether news helps.** Store the prediction with and without news adjustments. After 10 gameweeks, report whether the adjustments improved log loss. If they did not, propose removing or shrinking them.

## 7. Safety margin: confidence tiers

Every match gets a prediction. Each market prediction also gets a tier: High, Medium, or Low.

Tier inputs:

- Top-outcome probability (for 1X2) or distance of the predicted mean from the line (for over/under).
- Width of the 80% posterior interval on that probability.
- Disagreement between the stacked ensemble and the primary Bayesian model.
- Data quality flags: promoted team with fewer than 6 matches this season, manager change in the last 30 days, unanswered key question, unknown referee (cards only), source failure.

Rules:

- Define tier thresholds in Phase 4 from the backtest so that High, Medium, and Low show clearly separated hit rates and calibration. Report the thresholds and their basis.
- Any data quality flag caps the tier at Medium. Two or more flags force Low.
- The dashboard reports hit rate, log loss, and calibration **per tier**, so Lang sees what the margin buys and what it costs in coverage.
- Explain in `docs/LEARN.md` why this raises reliability of the High tier without hiding any prediction, and why a small High tier with a good record is worth more than a large one with a bad record.

## 8. Evaluation standard

Elite-firm quality means honest validation, not high headline numbers.

- **Walk-forward backtest** over 2023/24, 2024/25, and 2025/26: refit weekly using only data available before each gameweek, predict that gameweek, score, move forward. No random splits. No tuning on the test seasons after they have been scored once (use 2021/22 and 2022/23 for early tuning).
- **Metrics:**
  - 1X2: Ranked Probability Score (primary), log loss, Brier score, top-pick accuracy (secondary only).
  - Over/under and both teams to score: log loss, Brier score, calibration.
  - Count distributions (goals, corners, cards): log score of the realised count, and Continuous Ranked Probability Score.
  - Calibration: reliability diagrams and expected calibration error.
- **Baselines to beat, in order:** league base rates, Elo, then the bookmaker closing market (implied probabilities with the margin removed by the power method or Shin's method, documented).
- **Realistic targets** (Estimates, basis: published football forecasting literature and market efficiency; confirm against our own backtest in Phase 4):
  - Beat base rates and Elo on every market.
  - 1X2 top-pick accuracy around 50 to 55%, matching the market's range. The closing market is hard to beat. Matching it within a small RPS gap is a strong result for a free-data model.
  - Corners and cards over/under: the market is thinner, so these may be where the model competes best. Test this rather than assume it.
- **Red flags:** if any backtest shows top-pick accuracy above 60% on 1X2, stop and hunt for leakage before continuing.
- Publish `docs/MODEL_CARD.md`: data, methods, validation results with confidence intervals, known weaknesses, and what the model does not know (lineups announced about 60 minutes before kickoff, in-match events, weather).

## 9. Dashboard (Streamlit, Plotly charts)

Design for clarity on a phone first, then desktop. Clean, neutral theme with light and dark modes. Colour-blind-safe palette. Every chart has a one-line plain-English caption stating what it shows and an "Explain this" expander for the method behind it.

Pages:

1. **Fixtures (home page).** Next gameweek for both leagues, filterable by league, date, market, and confidence tier. Each row: teams, kickoff in Juba time (Africa/Juba, UTC+2) with a UTC toggle, 1X2 probability bar, expected goals, expected corners, expected cards, tier badge, news flag. Sortable. Download as CSV.
2. **Match deep-dive.** Scoreline probability heatmap, goals, corners, and cards distributions with the betting lines marked, model-by-model comparison, the top 5 drivers of the prediction in plain English (for example "Arsenal attack rating in top 10% of league"), news adjustments applied, referee profile, and uncertainty intervals.
3. **Team ratings.** Attack and defence ratings over time with 80% bands, for all teams in both leagues. Season-end table projection from 10,000 simulations: title, top 4, and relegation probabilities.
4. **Performance tracker.** Cumulative and per-gameweek RPS, log loss, and Brier by market, versus base rates, Elo, and the closing market. Calibration plots. Hit rate per confidence tier. Miss audit table with tagged causes. Ensemble weights over time.
5. **What-if simulator.** Pick a fixture, then adjust: remove a player (uses the importance weights), change the referee, change home advantage, add or remove rest days. Show before and after probabilities side by side. Clearly label it as a sandbox that never touches the ledger.
6. **Questions.** Today's questions from the Question Queue with one-tap answers and the deadline for each.
7. **Methods and changelog.** Renders `docs/LEARN.md`, `docs/MODEL_CARD.md`, and `docs/MODEL_CHANGELOG.md`. Pending model changes show an "awaiting Lang's approval" status.

Performance: the dashboard reads precomputed Parquet files only. No model fitting in the dashboard. Cache data loads.

## 10. Automation and schedule

- **Daily run:** GitHub Actions cron at 05:00 UTC (07:00 Juba time).
  1. Pull fixtures, results, odds, and news. Run freshness and validation checks.
  2. Score any newly finished matches against the ledger.
  3. Refit models and update posteriors.
  4. Generate questions for matches kicking off in the next 72 hours.
  5. **Lock** predictions for every match kicking off between 24 and 48 hours from the run time. Append to the ledger. Matches in this window that were already locked are not re-locked.
  6. Rebuild dashboard data files, commit, and push.
- **Weekly run** (Monday 06:00 UTC): stacking re-weight, miss audit, drift monitor.
- **Monthly run:** calibration check and model card refresh.
- Failure handling: if any step fails, the run still locks predictions from the last good model if possible, marks them with a "degraded" flag, and opens a GitHub Issue with the error. Never publish a prediction built on failed diagnostics.
- Scheduled-workflow keepalive: GitHub disables scheduled workflows on public repositories after a period without activity. Verify the current rule in Phase 0 and make sure the daily data commit keeps the repository active.
- Kickoff times change (TV picks, postponements). Re-read fixtures every run. If a locked match moves, keep the original locked prediction for scoring and add a new locked row only if the move exceeds 7 days.

## 11. Build phases and acceptance checks

Rough effort is in Claude Code working sessions. Estimate, adjust after Phase 0.

| Phase | Deliverable | Acceptance checks | Effort |
|---|---|---|---|
| 0. Data audit | `docs/DATA_SOURCES.md` with every source verified, rate limits, terms, freshness; team ID mapping; La Liga news and referee source decision | Every table in Section 3 marked Verified or replaced; mapping test passes for all 2021/22 to 2026/27 teams | 1 to 2 |
| 1. Pipeline | Ingestion, validation, DuckDB, leakage guard, ledger schema | `make data` runs clean; pandera checks pass; leakage test passes; CI green | 2 to 3 |
| 2. Goals model | Bayesian Dixon-Coles with time decay, xG variant, promoted-team priors | Diagnostics pass; walk-forward RPS beats base rates and Elo on 2023/24 to 2025/26; posterior predictive checks plotted | 3 to 4 |
| 3. Corners and cards | Hierarchical negative binomial models with referee effects | Dispersion reported; log score beats league-average baseline; calibration plots | 2 to 3 |
| 4. Challengers, stacking, tiers | Ordered logit, multinomial, XGBoost, Random Forest, stacked ensemble, calibration, tier thresholds | Full backtest report vs closing market; tier hit rates clearly separated; leakage red-flag check passes | 3 to 4 |
| 5. News and Question Queue | Scrapers, parser, impact model, GitHub Issue questions, answers file | Dry run on one real gameweek produces sensible adjustments within caps; questions are specific and ranked | 2 to 3 |
| 6. Dashboard | All 7 pages | Loads under 3 seconds on mobile throttling; every chart captioned; no em or en dashes | 3 to 4 |
| 7. Automation and deploy | Daily, weekly, monthly workflows; Streamlit Cloud deploy | Three consecutive clean daily runs; ledger rows locked 24 to 48 hours pre-kickoff; failure path tested by forcing an error | 1 to 2 |
| 8. Live season | Learning loop running to season end | Weekly report in `docs/weekly/`; miss audit and drift monitor populated | ongoing |

Priority rule: the season is already under way. Reach live locked predictions for 1X2 and goals as early as possible (end of Phase 2 plus a minimal version of Phase 7), then add corners, cards, news, and the full dashboard. Every gameweek without locked predictions is lost evaluation data.

## 12. Repository structure

```
football-predictor/
  pyproject.toml, uv.lock, Makefile, README.md
  .github/workflows/  daily.yml, weekly.yml, monthly.yml, ci.yml
  src/fp/
    ingest/        football_data_csv.py, football_data_api.py, understat.py, fpl.py, laliga_news.py
    validate/      schemas.py, freshness.py, leakage.py
    features/      ratings.py, rolling.py, schedule.py, news_impact.py
    models/        dixon_coles.py, corners_nb.py, cards_nb.py, ordered_logit.py, ml_models.py, elo.py
    ensemble/      stacking.py, calibration.py, tiers.py
    evaluate/      metrics.py, backtest.py, miss_audit.py, drift.py
    questions/     generate.py, github_issue.py, answers.py
    pipeline/      daily.py, weekly.py, monthly.py
  app/             Home.py and pages/ (Streamlit)
  data/            raw/, interim/, processed/, manual/ (managers.csv, answers.yaml)
  ledger/          predictions.parquet, results.parquet
  docs/            PRD.md, LEARN.md, MODEL_CARD.md, MODEL_CHANGELOG.md, DATA_SOURCES.md, DECISIONS.md, CHECKPOINT.md, weekly/
  tests/
```

## 13. Testing

- Unit tests for team mapping, feature `as_of` logic, probability outputs (each 1X2 set sums to 1 within 1e-6; count distributions sum to 1), tier rules, news adjustment caps.
- A simulation test: generate fake seasons from known team strengths, fit the Dixon-Coles model, and confirm it recovers the true parameters within their 90% intervals at least 85% of the time.
- CI runs tests, linting (`ruff`), type checks (`mypy` on `src/`), and the dash-character check on every push.

## 14. Out of scope

- Betting, staking, bankroll management, or any bookmaker account integration.
- Paid data, paid APIs, and paid LLM calls.
- Live in-play predictions.
- Player-level props (goalscorers, player cards).
- Leagues other than EPL and La Liga.

## 15. First action

Read this whole prompt. Then write `docs/PRD.md` and list, under Open questions, anything in this prompt you believe is wrong, infeasible on free data, or unclear. Stop and wait for Lang's approval.
