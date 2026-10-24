# Checkpoint

## Latest: 22 Oct 2026, Model Lab audit (version 23) and the Europe pipeline in the repository

- 24 Oct 2026, basketball phase B0 (data audit) on branch `basketball-b0`, not merged: the NBA and EuroLeague terms forbid using their statistics in connection with gambling, so only Wikipedia (CC BY-SA) is used; it gives dated, timed results for the EuroLeague (2,854 games) and the NBL (867), and dated NBA results without tip-off times; no free odds or box scores. Report `reports/basketball_data_audit_2026_10.md`; Lang's decisions B0-D1 to B0-D5 open.
- 24 Oct 2026, La Liga kickoff gap fixed (no model change): openfootball (31 days behind) listed every La Liga match from matchday 10 on a placeholder Sunday with no time, so nothing locked after Levante v Athletic (21 Oct 18:00 UTC) and matchday 10 got no forecasts [V: run 40064677070]; the calendar now takes the kickoff time and date from football-data.org wherever it marks the time as set, and openfootball's only where it has none (`fill_kickoffs` in `src/fp/ingest/matches.py`, column `kickoff_source`, `tests/test_kickoff_times.py`); missed matches stay unlocked (lock rule). This corrects open question 4: the lag did reach forecasts, through kickoff times.
- 24 Oct 2026, after the fix: manual run 40113104536 locked 5 La Liga matchday 10 matches at 16:47 UTC [V] (Barcelona v Real Madrid and Real Sociedad v Levante on time; Atlético v Deportivo, Athletic v Getafe and Celta v Betis late, flagged); Alavés v Málaga, Rayo v Elche, Racing v Espanyol and Valencia v Villarreal have no forecast. Lang chose the same day that football-data.org wins when both sources give a time and differ: 50 EPL times change, the first Everton v Coventry (Fri 6 Nov 20:00 UTC, openfootball Sat 7 Nov 15:00) [V]; no live lock changes; two trial locks (Toulouse v Troyes, PSG v Lyon) were made on openfootball's day, about 24 hours off, and stay as locked (append-only; under the 7-day re-lock rule).
- Model Lab version 23 published after a full audit (Lang's audit prompt, 22 Oct 2026): escaping,
  one rule and tax source, History corrections that never overwrite the settle task, yellow cards
  apart from booking points, strict team matching, per-competition forecast times, History past
  1,000 documents, keyed redraws, duplicate checks, Juba time from the time-zone database, WCAG AA
  contrast, data in files (first view 1.3 s on throttled 3G, was 5.1 s), a fast slip search in a
  worker, charts that fall back to tables. The page source is a private local repository
  (outside this public repository, no remote); its report is AUDIT_REPORT.md there. The public
  `tools/model_lab/template.html` is the old page and is no longer used for the Model Lab.
- The page data is built here: `scripts/build_model_lab.py --pages-dir DIR --data-json OUT` (with
  the private betting summary); the private build splits it into `data/gameweek.json`,
  `data/core.json` and `data/history-seed.json`, published as artifact files.
- Merged into main on 22 Oct (Lang's yes; first Europe run on GitHub the same day, 36 matches,
  1 started kept locked): `data/markets/markets.json` (one definition of codes,
  labels and settle rules; `scripts/gen_markets.py`), `pipeline_euro/` (Europa and Conference
  League: free sources, Wikipedia cross-check of this season's fixtures, lock rule, `make euro`,
  `.github/workflows/euro.yml` at 06:00 UTC) and the pre-registered Europe checks
  (`reports/euro_experiments_2026_10.md`): none passed; the bookmakers beat the goals model on
  13,038 domestic matches.
- Ready slip in the Slip finder (22 Oct, Lang's rules): total fair odds 1.20 to 1.70; two picks,
  or three when each is 1.20 or lower; one pick per match; stake from Lang's weekly budget rule.

### Open questions for Lang
1. The 21 Oct odds check accepts only slips above 1.70 total odds, which rule 1 does not allow:
   which rule stays?
2. The nightly history settle task (a Claude routine, checked 22 Oct) writes with update, so
   `corrections` survive. It never creates History documents: 25 forecast matches (28 Oct to
   4 Nov) are missing, and nothing adds new ones. Change its prompt to add them?
3. Replicate the new-club Elo start on the next 300 European matches?
4. openfootball is 3 to 4 weeks behind in every league (22 Oct). The cross-check test now judges
   only the dates both sources cover and warns about the lag (the daily results come from
   football-data.co.uk, so forecasts are not affected).

## Earlier: 20 Oct 2026, Champions League in the daily run and the Model Lab

### Done 15 to 20 Oct 2026
- Earlier work (reference Dixon-Coles, safety margins, Serie A and Ligue 1 in the Model Lab, UEFA reader) committed and merged (Lang: "Commit and merge all").
- Value finder on the Pairs page (Model Lab version 14, 20 Oct): Lang types Gal's odds; cutoff, value verdict and value pairs; no stake amounts.
- Champions League model `club_dc_v1` (branch `ucl-model`): one ID per club across 19 domestic leagues and the UEFA files (`data/manual/uefa_club_aliases.csv`); club Dixon-Coles with league levels (`fp.models.club_dc`); walk-forward test on 753 matches passed all four pre-registered checks (`reports/ucl_backtest_2026_10.md`).
- Safety margins for Champions League picks (`data/audit/ucl_safety_2026_10.json`): 90% for result, draw no bet and goal lines; double chance has none (flagged).
- Daily step `src/fp/pipeline/ucl.py` (after the trial step; cannot block the live run; Issue on failure): this season's fixtures and results from football-data.org (`CL`, names in `data/manual/fdorg_ucl_aliases.csv`); locks home, draw, away and goal lines into `ledger/ucl/`; writes `ledger/ucl/upcoming.parquet`. Ledger guard covers `ledger/ucl/`. Tests: `tests/test_ucl_pipeline.py`.
- Model Lab: Champions League cards in Predictions; its picks in Pairs, the slip checker and the value finder (checked in the browser with sample fixtures; published once the first daily run writes the export).
- First Champions League run (manual daily run 39449276758, 20 Oct 15:44 UTC, all steps green): 18 matchday 3 matches locked. Wednesday's 9 locked 25 to 27 hours before kickoff; Tuesday's 9 only 1 to 3 hours before (flagged `late_lock`; the step did not exist earlier). Four locks carry `europe_only_rating` (Sabah, Slavia Prague, Slovan Bratislava, Shakhtar Donetsk). Fit: 18,087 results, 602 clubs, converged.
- Model Lab version 15 published (20 Oct 2026, Lang chose "Publish with My bets as before"): 18 Champions League cards, the Champions League filter in Pairs, its matches in the value finder; My bets and the Bet log kept.

### Open questions for Lang
1. Serie A and Ligue 1 live review after 300 scored matches (about early January 2027).
2. Please answer the daily question Issue: unanswered questions cap confidence at Medium.

### Next actions
| Action | Owner |
|---|---|
| Champions League live check: compare locked forecasts with results as they come in (no market benchmark exists). | Claude |
| Serie A and Ligue 1 publishing review after 300 scored matches. | Claude, then Lang |
| Rayo v Athletic (10 Oct): result still missing in every source. | Claude |
| Settle Lang's logged bets when asked. | Claude, on request |

## Earlier: 9 Oct 2026, Phase 7 signed off; Phase 8 (live season) under way; goals fix, earlier schedule and provisional background models approved and switched on

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

### Done 12 Oct 2026
- Fast results live: football-data.org scores and Lang's chat entries (`data/manual/results_manual.csv`) fill in until football-data.co.uk publishes; first entries: Palace 3-1 Forest, Hull 2-2 Everton, Liverpool 0-3 Man City. Rayo v Athletic still had no result in any source on 12 Oct.
- Model Lab: double chance, European handicap and draw no bet picks; confidence shown as a track-record percentage with the lowest odds that pass Lang's rules; a private Bet log tab (owner-only database) that Claude settles on request.
- Approved order for new leagues: Serie A and Ligue 1 first (same data as La Liga), Champions League afterwards as its own project.
- Serie A and Ligue 1, step 1 done (data only, no live effect): league table with live and trial status (`src/fp/leagues.py`); trial tables in `data/processed/trial/` (`python -m fp.pipeline.data --trial`); 67 clubs and 187 spellings mapped; three matches with no football result left out (`data/manual/left_out_matches.csv`); CI builds the trial tables and probes football-data.org for `SA` and `FL1`. Findings: `docs/DATA_SOURCES.md` section 6; lesson: LEARN chapter 9.

- Serie A and Ligue 1, step 2 done (12 to 13 Oct): every live model backtested on both leagues, 2021/22 to 2025/26, live code and settings (`data/backtests/trial/`; GitHub runs 38310065127, 38310068965, 38310073216, 38310077149). Rules fixed beforehand, with one amendment made before any trial result was scored (`data/audit/preregistration_trial_2026_10.md`). Result (`reports/trial_backtest_2026_10.md`): home, draw, away and yellows pass; over 2.5 goals and corners fail; so by the rule neither league is proposed for background running. Pooled code now follows the leagues in the data (live outputs identical with a fixed hash seed); backtest workflows accept trial leagues.

- Lang chose "Run what passed" (13 Oct): Serie A and Ligue 1 home, draw, away (with double chance) and yellows run in the background daily (`src/fp/pipeline/trial.py`, ledger `ledger/trial/`), not published. Publishing review after 300 scored matches by rules fixed before the first lock (`data/audit/preregistration_trial_live_2026_10.md`).

- 14 Oct 2026: reference Dixon-Coles (MLGonzo/football_stats) adapted and tested at Lang's request; not adopted (`reports/dc_reference_2026_10.md`). Left uncommitted on the local branch `dc-reference`, as the request asked.
- 14 Oct 2026: corners and yellows (`reports/counts_safety_2026_10.md`): safety margin for picks passed its check and is live in the Model Lab (version 10); every corners and yellows line beats the league average (yellows about three times more); an EPL referee update adds nothing (not proposed). Code and results uncommitted in the same working tree.

- 14 Oct 2026 (later): safety margin on every pick (Model Lab version 11); Serie A and Ligue 1 in the Model Lab for their tested markets (version 12); Champions League approved for goals markets only: step 1 started (`fp.ingest.uefa` reads 3,621 European matches); next, one ID per club across European and domestic sources.

### Open questions for Lang
1. Serie A and Ligue 1 live review after 300 scored matches (about early January 2027).
2. Uncommitted work on the local branch `dc-reference`: the reference Dixon-Coles comparison, the safety margins, Serie A and Ligue 1 in the Model Lab (and the background run's new upcoming export), and the UEFA reader. The daily run only writes the Serie A and Ligue 1 export once this is committed and merged.
2. Please answer the daily question Issue: unanswered questions cap confidence at Medium (all nine 9 Oct locks were capped).

### Next actions
| Action | Owner |
|---|---|
| Serie A and Ligue 1 background run: check the first trial locks (Thu 15 Oct run, for Fri 16 Oct kickoffs) and results; publishing review after 300 scored matches. | Claude |
| Champions League step 1: map every club in the European files (377 names) and their domestic leagues to one ID; then the walk-forward test. | Claude, next |
| Settle Lang's logged bets when asked (procedure in Claude's memory). | Claude, on request |
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
