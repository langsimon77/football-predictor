# Checkpoint

## Latest: 25 Sep 2026, Phase 2 (Bayesian Dixon-Coles) complete, awaiting Lang's approval

### Done this session
- Phase 1F approved. Phase 2 built, tuned, tested, and documented.
- Model: Bayesian hierarchical Dixon-Coles in PyMC with time decay, shots-on-target layer (D1), and promoted-team priors from second-tier form. Diagnostics gate: R-hat below 1.01, bulk ESS above 400, zero divergences; one retry in the other parameterisation; fallback to the last good posterior.
- Tuning (2021/22 and 2022/23): shots-on-target variant chosen over goals-only and the random-walk challenger.
- Test (2023/24 to 2025/26), run once on GitHub: results below.
- Sampler benchmark on the runner: NumPyro chosen (about twice as fast as nutpie for the chosen model).
- Daily run can lock `dc_bayes_v1` with 80% intervals, but the switch is **off** until Lang approves.
- Ledger schema gained an `intervals` column while still empty; hashing now skips empty cells, so future columns never break old rows.
- Long backtests moved to GitHub Actions after the old session's scratch folder was cleared (tuning predictions lost, now regenerating in run 36183165274).

### Phase 2 acceptance checks
| Check | Result |
|---|---|
| Diagnostics pass | 209 of 209 test fits and 272 of 272 tuning fits passed (after at most one retry). |
| Walk-forward RPS beats base rates | Passed: 0.1970 against 0.2289; interval of the difference −0.0366 to −0.0272. |
| Walk-forward RPS beats Elo | **Partly.** Lower on average (0.1970 against 0.1982) but the 95% interval (−0.0030 to +0.0006) includes zero. Significant in the EPL (−0.0030, interval −0.0055 to −0.0003); level in La Liga. |
| Posterior predictive checks plotted | Done: `reports/figures/ppc_EPL.png`, `ppc_LaLiga.png`. EPL typical; La Liga 2025/26 had unusually few 0-0s. |
| Simulation recovery (spec S13) | Passed: 85% to 95% of true values inside 90% intervals. |
| Leakage alarm | Clear: top-pick accuracy 53.1%. |

Local: all tests pass except 2 that skip here (football-data.org unreachable from this Mac). `ruff`, `mypy`, and the dash check pass.

### Known weaknesses
- Dixon-Coles probabilities are too timid (calibration slope 1.22; Elo 1.00). Fix: calibration map, Phase 4.
- The 80% intervals reflect parameter uncertainty only; the market lands inside them 66% of the time.
- No corners, cards, news, or tiers yet (Phases 3 to 5).

### Open questions for Lang
1. Approve Phase 2?
2. Switch `dc_bayes_v1` live as the primary model before the first lock (Thu 8 Oct 04:41 UTC)? `dc_mle_v0` and `elo_v0` keep running beside it either way.
3. Pull the calibration step forward into Phase 3, since it addresses the main weakness found here?

### Next actions
| Action | Owner |
|---|---|
| Answer the three questions above. | Lang |
| If approved: flip `BAYES_LIVE`, dry-run on GitHub, confirm the posterior cache works. | Claude |
| Phase 3: corners and cards models. | Claude, after approval |

### Facts still unverified
- The `HxG` provider and whether it includes penalties.
- Whether the daily bot commits count as "activity" for GitHub's 60-day rule.
- GitHub Pages speed from Juba (Phase 6).

## History
- 23 Sep 2026, session 1: PRD written with 26 open questions; approved.
- 23 Sep 2026, session 2: Phase 0 data audit. Understat and FPL barred; openfootball added; 72 mapping tests.
- 24 Sep 2026, session 3: Phase 1 pipeline; CI green on GitHub. Phase 1F models, backtest, daily workflow live.
- 24 to 25 Sep 2026, session 4: Phase 2 Bayesian model, tuning, GitHub-run test stage.
