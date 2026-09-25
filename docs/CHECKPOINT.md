# Checkpoint

## Latest: 25 Sep 2026, Bayesian model live; Phase 3a (calibration) complete, awaiting Lang's approval

### Done this session
- Phase 2 approved. `dc_bayes_v1` is live as the primary model; `dc_mle_v0` and `elo_v0` run beside it. It refits on every daily run. Verified on GitHub with a dry run and a real run; first posteriors cached for the fallback.
- The live report shows the primary model with its 80% home-win range and scores every model side by side.
- Phase 3a (calibration, moved forward by Lang): built power and Dirichlet calibration with tests; scored on the tuning and test seasons; tested the spec's monthly walk-forward version.
- Backtests now store the full scoreline table; 3,800 walk-forward predictions kept in `data/backtests/`.

### Phase 3a findings
| Question | Answer |
|---|---|
| Does a fixed map from the tuning seasons help? | No. The model was not timid in 2021/22 and 2022/23, so the map is nearly "no change". Test log loss −0.0003, interval −0.0027 to +0.0021. |
| Does a monthly map help? | It fixes the timidity (slope 1.24 to 1.09, level with the market) but the accuracy gain is not clear (log loss interval −0.0035 to +0.0017), and BTTS gets slightly worse (+0.0009). |
| Apply either live? | **Recommend no.** Neither passes the clear-improvement rule. Revisit in Phase 4 with the Elo blend. |

### Known weaknesses
- The Bayesian model is too timid since 2023/24 (slope 1.24). Accepted for now; Phase 4.
- The 80% intervals reflect parameter uncertainty only.
- No corners, cards, news, or tiers yet.

### Open questions for Lang
1. Accept the recommendation not to switch calibration on, and revisit it in Phase 4?
2. Approve moving on to Phase 3b: corners and cards models?

### Next actions
| Action | Owner |
|---|---|
| Answer the two questions above. | Lang |
| Watch `reports/latest.md` from Thu 8 Oct. | Lang |
| Phase 3b: hierarchical negative binomial models for corners and cards (spec S5.3, S5.4). | Claude, after approval |

### Facts still unverified
- The `HxG` provider and whether it includes penalties.
- Whether the daily bot commits count as "activity" for GitHub's 60-day rule.
- GitHub Pages speed from Juba (Phase 6).

## History
- 23 Sep 2026, session 1: PRD written with 26 open questions; approved.
- 23 Sep 2026, session 2: Phase 0 data audit. Understat and FPL barred; openfootball added; 72 mapping tests.
- 24 Sep 2026, session 3: Phase 1 pipeline; CI green on GitHub. Phase 1F models, backtest, daily workflow live.
- 24 to 25 Sep 2026, session 4: Phase 2 Bayesian model, tuning, GitHub-run test stage.
- 25 Sep 2026, session 5: Bayesian model live as primary. Phase 3a calibration studied, not applied.
