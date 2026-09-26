# Checkpoint

## Latest: 26 Sep 2026, Phase 5 built and dry-run; awaiting Lang's go-live decision

### Done this session
- Phase 4 approved and live: shadows (four challengers, `stack_v1`) and tiers on every Bayesian row.
- Phase 5 built (`src/fp/news/`):
  - Question Queue: one Issue a day for matches locking at the next run, at most 10, ranked by expected shift; per club, starters out and main goal threat; trust rule on who opened and edited the Issue.
  - Impact: capped multipliers on the Bayesian scoring rates; `dc_bayes_v1_nonews` locked when news moves a forecast.
  - Managers: Wikipedia infobox check for clubs playing in 72 hours; 40 clubs seeded in `data/manual/managers.csv`.
  - Tier flags: unanswered question, manager change.
- Dry run on the first real gameweek: `reports/phase5_dry_run.md`. All four acceptance checks pass.
- Behind `NEWS_LIVE = False` in `src/fp/news/live.py` until Lang approves.

### Phase 5 acceptance checks
| Check | Result |
|---|---|
| Sensible adjustments within caps | Yes: every multiplier between 0.88 and 1.12; the worst case (3+ out plus main threat) hits the cap. |
| Questions specific and ranked | Yes: clubs, league, kickoff in Juba time and UTC, team-news links; at most 10 a day; ranked by expected shift. |

### Known weaknesses
- News effect sizes are Assumptions; the news-on against news-off test after 10 gameweeks decides.
- Issue opening and closing have not run for real yet (reading works).
- Blending adds little; still 0.014 behind the Friday market; over/under tiers barely separate.

### Open questions for Lang
1. Switch the Question Queue on? First Issue Wed 7 Oct (Málaga v Espanyol), 10 questions Thu 8 Oct.
2. Accept the Assumption effect sizes, or check the API-Football terms so I can calibrate them?
3. Unanswered question as a flag (spec S7), not "drop one level" (S6): keep?

### Next actions
| Action | Owner |
|---|---|
| Answer the three questions. | Lang |
| On approval: switch on, open one test Issue and close it, watch the 7 and 8 Oct runs. | Claude |
| Phase 6: dashboard and GitHub Pages fixtures page. | Claude, after approval |
| After 10 gameweeks: news-on against news-off report. | Claude |
| End of 2026/27: re-test `stack_v1` against `dc_bayes_v1`. | Claude |

### Working notes
- XGBoost runs locally only when Python is started directly with scikit-learn's OpenMP library: `DYLD_LIBRARY_PATH=$PWD/.venv/lib/python3.12/site-packages/sklearn/.dylibs .venv/bin/python ...`. `uv run` drops the variable. GitHub needs nothing special.

### Facts still unverified
- The `HxG` provider and whether it includes penalties.
- Whether the daily bot commits count as "activity" for GitHub's 60-day rule.
- GitHub Pages speed from Juba (Phase 6).

## History
- 23 Sep 2026, session 1: PRD written with 26 open questions; approved.
- 23 Sep 2026, session 2: Phase 0 data audit. Understat and FPL barred; openfootball added; 72 mapping tests.
- 24 Sep 2026, session 3: Phase 1 pipeline; CI green on GitHub. Phase 1F models, backtest, daily workflow live.
- 24 to 25 Sep 2026, session 4: Phase 2 Bayesian model, tuning, GitHub-run test stage.
- 25 Sep 2026, session 5: Bayesian model live as primary. Phase 3a calibration studied, not applied. Phase 3b corners and cards built and tested.
- 26 Sep 2026, session 6: Phase 4 challengers, stacking, calibration revisited, tiers. Lang approved: Bayesian stays published, shadows and tiers live. Phase 5 news and Question Queue built and dry-run.
