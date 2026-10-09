# Checkpoint

## Latest: 9 Oct 2026, Model Lab rewritten in plain language with a Predictions page; model check-up done, three proposals wait for Lang

### Done this session
- First real locks on Thu 8 Oct (Málaga v Espanyol, Arsenal v Leeds); scheduled daily runs succeed every day but start 5 to 7 hours late.
- Model Lab rewritten in plain language (plain model names, technical names small and grey, glossary) with a new Predictions page: the current gameweek, EPL Matchday 6 and La Liga Matchday 8. Republished to the same address.
- Model check-up (`scripts/audit_2026_10.py`, `reports/audit_2026_10.md`, LEARN chapter 8): goals are less spread out than Poisson; a goals fix passed the test seasons and a pre-registered replication on 2018/19 and 2019/20 (GitHub run 37909076802, stored as `data/backtests/dc_bayes_v1_walkforward_2018_2020.parquet`). Corners and yellows: nothing to change.
- Errors fixed: the bookmaker gap in MODEL_CARD (0.016, not 0.014); the Model Lab builder now refuses stale local data.

### Open questions for Lang
1. Approve the goals fix `shape_v1`? (MODEL_CHANGELOG, 9 Oct 2026.)
2. Approve the earlier daily schedule (00:41 UTC)? The 11:30 UTC Saturday kickoff can otherwise lock late until 25 Oct.
3. Approve running the background models for provisional forecasts?
4. Phase 7 sign-off: every scheduled day since 27 Sep has succeeded (main runs 09:30 to 11:48 UTC).

### Next actions
| Action | Owner |
|---|---|
| Decide the three proposals and the Phase 7 sign-off. | Lang |
| If `shape_v1` is approved: implement, add the background copy, recompute tier cut points and drift norms, dry run on GitHub, then switch on. | Claude, after approval |
| First weekly report with live scores, Mon 12 Oct. | Automatic |

## Earlier: 26 Sep 2026, Phase 7 built, tested, and deployed; sign-off waits on three clean scheduled days (27 to 29 Sep)

### Done this session
- Phases 4, 5, 6 approved and live. GitHub Pages on: https://langsimon77.github.io/football-predictor/ (first deploy passed).
- Phase 7 built:
  - Weekly run (`weekly.yml`, Monday 06:00 UTC): scores, miss audit, drift monitor, guarded shadow-stack re-weight with logged evidence, `docs/weekly/<date>.md`.
  - Monthly run (`monthly.yml`, 1st, 06:00 UTC): calibration check (report only), model card live record, schedule keep-alive.
  - Failure handling: degraded runs open an Issue; forced failures on dry runs only; re-lock when a kickoff moves more than 7 days.
  - Dashboard shows drift and stack-weight history. LEARN chapter 7.

### Phase 7 acceptance checks
| Check | Result |
|---|---|
| Three consecutive clean daily runs | **Not yet met.** Scheduled runs so far: 25 Sep (success, started 5 hours late); 26 Sep (started 4 hours 49 minutes late; the guard skipped it because manual runs had already done the day's work). Manual live runs on 25 and 26 Sep passed. Backup schedules added (10:41, 16:41 UTC) with a same-day guard. Check 27, 28, 29 Sep. |
| Ledger rows locked 24 to 48 hours before kickoff | GitHub replay, 17 to 19 Sep: all 160 on-time rows locked 30.8 to 38.3 hours before kickoff. The only late locks (2 matches) kicked off on the replay's first day, with no earlier run. The real ledger's first locks are on 8 Oct. |
| Failure path tested by forcing an error | Yes. Forced crash: run failed, Issue #3 opened. Forced Bayesian failure: both leagues fell back to the last good posterior, run finished, "degraded" Issue #4 opened. Both closed. |
| Weekly and monthly runs | Dry runs on GitHub passed (runs 36228987459, 36228990835). |
| Streamlit Cloud deploy | Done: https://football-predictor-hvplshfcfv7vsqqkaplmbq.streamlit.app/ (deployed by Lang; four pages checked with live data). |

### Model Lab
- Interactive snapshot of every analysis: https://claude.ai/artifact/Kt9foBMJQ9uy1nbDohAFhH (private). Rebuild with `scripts/build_model_lab.py OUT.html --pages-dir DIR` (download fixtures.parquet, details.parquet, meta.json from the Pages site's data folder first), then republish to that address.

### Known weaknesses
- GitHub starts the daily schedule about 5 hours late (25 and 26 Sep) and may drop it. Backup schedules cover a dropped run; Juba-time question deadlines can still slip.
- Stack weight fit is ill-conditioned; a steadier fit was tested and not adopted under the pre-set rule (`reports/stack_steadiness.md`).
- No free source of penalties or line-ups for the miss audit.

### Open questions for Lang
1. None open. Phase 7 sign-off waits on three clean scheduled days (27 to 29 Sep).

### Next actions
| Action | Owner |
|---|---|
| Check the scheduled daily runs of 27, 28, 29 Sep (main or backup); then ask Lang to sign off Phase 7. A one-time scheduled task (`phase7-daily-runs-check`, Tue 29 Sep 13:00 UTC, read-only) runs this check in the Claude app and reports. | Automatic, then Lang |
| First question Issue Wed 7 Oct; first locks Thu 8 Oct; first weekly report Mon 12 Oct. | Automatic |
| Refresh the Model Lab after the first locks: one-time task `refresh-model-lab-first-locks`, Thu 8 Oct 15:00 UTC; it publishes only if the 8 Oct locks are in the ledger. | Automatic, then Lang |
| Phase 8: live season (weekly reports, miss audit, drift). | After Phase 7 sign-off |

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
- 26 Sep 2026, session 6 (cont.): Pages on; Phase 7 weekly, monthly, failure handling built and tested on GitHub.
