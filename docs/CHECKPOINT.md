# Checkpoint

## Latest: 9 Oct 2026, Phase 7 signed off; Phase 8 (live season) under way; goals fix, earlier schedule and provisional background models approved and switched on

### Done this session
- First real locks on Thu 8 Oct (Málaga v Espanyol, Arsenal v Leeds) and Fri 9 Oct (9 more); every lock 24 to 48 hours before kickoff.
- Model Lab rewritten in plain language with a Predictions page (current gameweek): https://claude.ai/artifact/Kt9foBMJQ9uy1nbDohAFhH.
- Model check-up (`reports/audit_2026_10.md`, LEARN chapter 8). Lang approved all three proposals and Phase 7 on 9 Oct 2026.
- Switched on for the 10 Oct run: `shape_v1` (`src/fp/models/shape.py`, numbers in `data/shape/shape_v1.json`, plain copy `dc_bayes_v1_noshape`); goals tier cut points refit (`reports/shape_v1_rollout.md`); weekly drift norms and stack pool from `data/backtests/baselines_2021_2025_shape_v1.parquet`; daily cron 00:41 UTC (backups 06:41, 12:41); shadow models for provisional rows; Streamlit what-if uses the fix.

### Checked 10 Oct 2026
- First run on the new schedule started 06:23 UTC (scheduled 00:41). Sunday's 7 matches locked 29.6 to 36.6 hours before kickoff, none late.
- 63 rows: every `dc_bayes_v1` row carries `shape_v1`, each with its `dc_bayes_v1_noshape` copy. October numbers read from `data/shape/shape_v1.json` (no refit within the month).
- Dashboard: all 12 provisional matches carry the fix and all 9 models; the what-if receives the fix. CI green on 29bb322. Model Lab refreshed.
- All 7 locks again carry the unanswered-question flag (Issue #7 unanswered).

### Open questions for Lang
1. None open. Please answer the daily question Issue: unanswered questions cap confidence at Medium (all nine 9 Oct locks were capped).

### Next actions
| Action | Owner |
|---|---|
| First weekly report with live scores, Mon 12 Oct. | Automatic |
| First monthly `shape_v1` refit, Sun 1 Nov (logged in `data/shape/shape_v1.json`). | Automatic |
| News-on against news-off test after 10 gameweeks; `shape_v1` against its plain copy at the end of 2026/27. | Claude, then Lang |

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
