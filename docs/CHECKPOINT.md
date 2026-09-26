# Checkpoint

## Latest: 26 Sep 2026, Phase 4 approved and live; awaiting approval to start Phase 5

### Done this session
- Phase 4 built and tested: four challengers, stacked ensemble, calibration revisited (not applied), confidence tiers. Report `reports/backtest_phase4.md`.
- Lang approved both recommendations ("proceed as recommended"):
  1. `dc_bayes_v1` stays the published forecast. The four challengers and `stack_v1` lock daily as shadow rows (`src/fp/pipeline/shadows.py`).
  2. Tiers fill the `tiers` column of every Bayesian row, for every market. The promoted-club flag is shown but not counted.
- Live and backtest paths build identical challenger inputs (40 recent matches, all 28 features).
- Local replay 17 to 19 Sep 2026: 22 matches, 8 rows each, chain verified, tiers on every Bayesian row, report shows them.
- New `replay.yml` workflow to replay the daily loop on GitHub without committing.

### Phase 4 acceptance checks
| Check | Result |
|---|---|
| Full backtest against the closing market | Test log loss: stack 0.9738, Bayesian 0.9759, Friday market 0.9601, closing market 0.9571. Stack minus Bayesian −0.0022 (interval −0.0064 to +0.0019), not clear. Stack minus Elo −0.0049 (clear). |
| Tier hit rates clearly separated | 1X2 yes (Bayesian High 74%, Medium 53%, Low 43%; no overlap). Over/under: 4 of 11 lines. |
| Leakage red flag | Passed: highest top-pick accuracy 54.4%. |

### Known weaknesses
- Blending adds little: the seven models share one signal.
- Still 0.014 behind the market at the Friday snapshot.
- Over/under tiers barely separate on most lines.
- The Bayesian model stays timid (slope 1.23); its High tier wins more than promised.

### Open questions for Lang
1. Approve starting Phase 5 (news and the Question Queue through GitHub Issue checkboxes)?

### Next actions
| Action | Owner |
|---|---|
| Approve Phase 5, or reply with changes. | Lang |
| Watch `reports/latest.md` from Thu 8 Oct: first real locks, now with tiers. | Lang |
| Phase 5: news, Question Queue; unanswered key questions become a tier flag. | Claude, after approval |
| End of 2026/27: re-test `stack_v1` against `dc_bayes_v1` with the strict rule. | Claude |

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
- 26 Sep 2026, session 6: Phase 4 challengers, stacking, calibration revisited, tiers. Lang approved: Bayesian stays published, shadows and tiers live.
