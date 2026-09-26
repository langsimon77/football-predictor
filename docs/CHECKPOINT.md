# Checkpoint

## Latest: 26 Sep 2026, Phase 6 built and tested; awaiting Lang's go-live decision (GitHub Pages)

### Done this session
- Phases 4 and 5 approved and live (shadows, tiers, Question Queue; first Issue Wed 7 Oct).
- Phase 6 built:
  - `src/fp/publish/`: the daily run writes precomputed dashboard files (`app/data/`) and a static fixtures page (`site/`).
  - `app/`: seven Streamlit pages (Fixtures, Match, Team ratings, Performance, What-if, Questions, Methods), reading only those files; own `requirements.txt`.
  - `docs/MODEL_CARD.md`; LEARN chapter 6.
  - Daily workflow: dashboard cache, ratings history committed, Pages deploy gated by the `PAGES_ENABLED` variable (off).
- Tested: 5-day local replay (all seven pages load with no errors on a phone-sized screen; every chart captioned); GitHub one-day replay (run 36227565338) publishes every file; export takes seconds.

### Phase 6 acceptance checks
| Check | Result |
|---|---|
| Loads under 3 seconds on mobile | Static page: one 19 KB request, no other files, rendered in 18 ms locally [V]; about 1 second on 4G [E]. Streamlit cannot meet this from a cold start (PRD Q4); the static page is the fast door. |
| Every chart captioned | Yes: every chart has a one-line caption and an "Explain this" note (checked on all seven pages). |
| No em or en dashes | Yes: dash check covers the app, the page, and JSON. |

### Known weaknesses
- The Streamlit app wakes slowly after a quiet night (free host).
- Stack weights fitted on one season shift between reruns; Phase 7's weekly re-weight needs a steadier fit (to be proposed).
- Ratings history starts on the first live run; no backfill.

### Open questions for Lang
1. Turn on GitHub Pages (publishes the fixtures page and dashboard files at https://langsimon77.github.io/football-predictor/)?
2. Approve starting Phase 7 (weekly and monthly automation, Streamlit Cloud deploy)?

### Next actions
| Action | Owner |
|---|---|
| Answer the two questions. | Lang |
| On a yes to Pages: switch Pages to "GitHub Actions", set `PAGES_ENABLED`, check the first deploy. | Claude |
| Streamlit Cloud: sign in at share.streamlit.io with GitHub and deploy `app/Home.py` (Phase 7; only Lang can create the account). | Lang, guided |
| Tick the daily Issue from Wed 7 Oct. | Lang |

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
- 26 Sep 2026, session 6: Phase 4 challengers, stacking, calibration revisited, tiers. Lang approved: Bayesian stays published, shadows and tiers live. Phase 5 news and Question Queue built, tested, and live.
- 26 Sep 2026, session 6 (cont.): Phase 6 dashboard and static fixtures page built and tested; Pages off until Lang approves.
