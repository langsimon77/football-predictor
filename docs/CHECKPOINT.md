# Checkpoint

## Latest: 26 Sep 2026, Phase 4 built and tested; awaiting Lang's two decisions

### Done this session
- Four challengers (ordered logit, multinomial, Random Forest, XGBoost) on 28 lock-time features. Settings chosen on 2017/18 to 2020/21 only. Walk-forward with monthly refits on GitHub (run 36195202742, 5.5 minutes); predictions kept in `data/backtests/`.
- Stacked ensemble with a 5% floor and the capped weekly re-weight (`src/fp/ensemble/stacking.py`), replayed over the test seasons.
- Calibration revisited on the stack: no map passes the strict rule.
- Confidence tiers (`src/fp/ensemble/tiers.py`, 6 tests): cut points from the tuning seasons in `data/tiers/thresholds.json` (not used live yet).
- Report `reports/backtest_phase4.md` and figure `reports/figures/phase4_reliability.png` from `scripts/backtest_phase4.py` (36 s).
- LEARN chapter 4; MODEL_CHANGELOG and DECISIONS updated.

### Phase 4 acceptance checks
| Check | Result |
|---|---|
| Full backtest against the closing market | Test log loss: stack 0.9738, Bayesian 0.9759, Friday market 0.9601, closing market 0.9571. Stack minus Bayesian −0.0022 (interval −0.0064 to +0.0019), not clear. Stack minus Elo −0.0049 (clear). |
| Tier hit rates clearly separated | 1X2 yes (Bayesian High 74%, Medium 54%, Low 43%; no overlap). Over/under: 2 of 8 lines only. |
| Leakage red flag | Passed: no forecast above 60% top-pick accuracy (highest 54.4%). |

### Known weaknesses
- Blending adds little: the seven models share one signal, and the stack weights swing between near-identical models.
- Still 0.014 behind the market at the Friday snapshot.
- Over/under tiers barely separate.
- The Bayesian model stays timid (slope 1.23); its High tier wins more than promised.

### Open questions for Lang
1. Published forecast: keep the Bayesian model and log the stack and four challengers as shadows (recommended), or publish the stack?
2. Tiers in the ledger: switch on, with the promoted-club flag dropped from the caps (recommended) or exactly as specified?

### Next actions
| Action | Owner |
|---|---|
| Answer the two questions. | Lang |
| After approval: daily integration (lock-time challenger features, monthly challenger refits, shadow rows, tier columns), replay and dry run on GitHub before 8 Oct. | Claude |
| Phase 5: news and the Question Queue. | Claude, after Phase 4 approval |

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
- 26 Sep 2026, session 6: Phase 3b approved and live (25 Sep). Phase 4 challengers, stacking, calibration revisited, tiers; report written; awaiting decisions.
