# Checkpoint

## Latest: 24 Sep 2026, Phase 1F (fast track) complete and live, awaiting Lang's approval

### Done this session
- Phase 1 approved. Phase 1F built, backtested, and deployed.
- Models: `dc_mle_v0` (fast Dixon-Coles, primary) and `elo_v0` (benchmark). See `docs/MODEL_CHANGELOG.md`.
- Backtest: `reports/backtest_1f.md`. Tuned on 2021/22 and 2022/23; tested on 2023/24 to 2025/26.
- Replay of the daily run over 14 Aug to 21 Sep 2026: all 119 matches locked once per model, 30.8 to 38.8 hours before kickoff, no late locks, no failed fits.
- Daily workflow live on GitHub at 04:41 UTC. Dry run and real run both pass on the runner. The first real run exposed a bug (`git add ledger` before the folder existed); fixed. That failure opened issue #1 as designed; closed with a note.
- `docs/LEARN.md` chapter 1F written.

### Phase 1F checks
| Check | Result |
|---|---|
| Beats league base rates on 1X2 | Passed: RPS 0.197 against 0.229; 95% interval of the difference −0.036 to −0.027. |
| Compared with Elo | Level: −0.0008, interval −0.0024 to +0.0008. Not a pass condition for 1F; Phase 2 must beat Elo. |
| Compared with sharp closing market | 0.006 behind (interval 0.004 to 0.008). |
| Leakage red flag (top pick above 60%) | Clear: 53.0%. |
| Daily run on GitHub | Passed, dry and real. 25 to 40 seconds a run. |
| Next round has confirmed kickoff times | Yes: all 20 matches. First lock Thu 8 Oct 04:41 UTC (Málaga v Espanyol). |

Local: 125 tests pass, 2 skip (football-data.org unreachable here). `ruff`, `mypy`, and the dash check pass.

### Known weaknesses
- Fixed shrinkage pulls strong clubs towards average (Man City 63% where Elo and the market said 73%). Phase 2's hierarchical priors address this.
- No corners, cards, news, or tiers yet (Phases 3 to 5).

### Open questions for Lang
- Approve Phase 1F, which moves us to Phase 2 (Bayesian Dixon-Coles).

### Next actions
| Action | Owner |
|---|---|
| Approve Phase 1F, or reply with changes. | Lang |
| Watch `reports/latest.md` on GitHub from Thu 8 Oct. | Lang |
| Phase 2: Bayesian hierarchical Dixon-Coles in PyMC, shots-on-target variant (D1), sampler benchmark on the runner, simulation recovery test, posterior predictive checks. | Claude, after approval |

### Facts still unverified
- The `HxG` provider and whether it includes penalties.
- Whether the daily bot commits count as "activity" for GitHub's 60-day rule (they are commits to the default branch, so very likely yes).
- GitHub Pages speed from Juba (Phase 6).

## History
- 23 Sep 2026, session 1: PRD written with 26 open questions; approved.
- 23 Sep 2026, session 2: Phase 0 data audit. Understat and FPL barred; openfootball added; 72 mapping tests.
- 24 Sep 2026, session 3: Phase 1 pipeline; CI green on GitHub. Phase 1F models, backtest, daily workflow live.
