# Checkpoint

## Latest: 25 Sep 2026, Phase 3b (corners and cards) complete, awaiting Lang's approval

### Done this session
- Lang agreed to leave calibration off until Phase 4, and approved Phase 3b.
- As-of features for corners and cards: rolling team averages, Elo gap at lock, league table at lock, derby list. Leakage-checked; a planted-future test passes; live and backtest paths give identical features.
- Models: total-corners (Poisson) and total yellows (negative binomial, EPL referee effect).
- Tuning (2021/22, 2022/23) and test (2023/24 to 2025/26) backtests on GitHub.
- Daily integration built behind `COUNTS_LIVE` (off). Corners and cards go on the primary ledger row. Replay passes; about one minute per daily run.
- Report gains expected corners and expected yellows columns.
- Walk-forward predictions for corners and cards kept in `data/backtests/`.

### Phase 3 acceptance checks
| Check | Result |
|---|---|
| Dispersion reported | Cards: negative binomial shape about 29 to 37 (mild extra spread). Corners per team: about 13, but home and away corners correlate negatively (−0.35 EPL, −0.27 La Liga), so the total is modelled directly and is close to Poisson (shape about 51). |
| Log score beats league-average baseline | Cards: −0.019 (interval −0.028 to −0.010). Corners: −0.009 (interval −0.015 to −0.002). Both pass. |
| Calibration plots | `reports/figures/calibration_cards.png`, `calibration_corners_total.png`: close to the diagonal on every line. |
| Diagnostics | Test fits: corners 209 of 209, cards 208 of 209 (the one failure fell back to the previous good fit). |

Also: cards beat a team-average baseline (−0.017); corners do not (level). Local: all tests pass except 2 that skip here. `ruff`, `mypy`, dash check pass.

### Known weaknesses
- Corners are barely more predictable than the clubs' own recent averages.
- Dixon-Coles 1X2 still too timid since 2023/24 (Phase 4).
- The derby list is my seed (Assumption).

### Open questions for Lang
1. Approve Phase 3b and switch corners and cards live before the first lock (Thu 8 Oct)?
2. Check the derby list in `data/manual/derbies.csv`: add, remove, or approve as is.

### Next actions
| Action | Owner |
|---|---|
| Answer the two questions above. | Lang |
| If approved: flip `COUNTS_LIVE`, dry-run on GitHub, confirm the count posteriors are cached. | Claude |
| Phase 4: challengers (ordered logit, multinomial, XGBoost, Random Forest), stacking, calibration revisited, confidence tiers. | Claude, after approval |

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
