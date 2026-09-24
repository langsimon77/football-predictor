# Checkpoint

## Latest: 24 Sep 2026, Phase 1 (pipeline) complete, awaiting Lang's approval

### Done this session
- Phase 0 approved. D1 to D6 adopted. Repo: https://github.com/langsimon77/football-predictor.
- Keys checked (values never printed). API-Football key works, but its free plan excludes 2026/27, so team news goes through the Question Queue (D2). football-data.org still times out from this Mac. CI will probe it from GitHub's runner.
- Installed GitHub CLI 2.101.0 (checksum verified). Lang signed in as langsimon77 and set both API keys as GitHub Actions secrets.
- Built Phase 1: processed tables, pandera validation, freshness check, as_of lock clock, hash-chained ledger, DuckDB views, CI workflow, ledger CI guard.
- `docs/LEARN.md` chapter 1 written. Chapter 0 corrected to the 04:41 UTC run time.
- Pushed to GitHub. CI is green on the runner. football-data.org works from the runner (380 PL, 380 PD, 144 Champions League matches); its 40 team spellings are now mapped.

### Phase 1 acceptance checks
| Check | Result |
|---|---|
| `make data` runs clean | Passed: 19 s with fresh downloads. 7,719 matches, 760 fixtures, 10,301 second-tier matches, 10 referee appointments. |
| pandera checks pass | Passed on real data. Negative tests prove duplicates, negative counts, naive times, unmapped teams, missing matches, and impossible odds are rejected. |
| Leakage test passes | Passed: every lock lands 24 to 48 h before kickoff; future inputs are caught. |
| CI green | Passed on GitHub's runner (Ubuntu 24.04), full run in under 4 minutes. |

Local totals: 106 tests pass; `ruff`, `mypy`, and the dash check pass.

### Open questions for Lang
- Approve Phase 1 so Phase 1F (fast-track model and daily lock) can start.

### Next actions
| Action | Owner |
|---|---|
| Approve Phase 1, or reply with changes. | Lang |
| Phase 1F: Elo plus maximum-likelihood Dixon-Coles, daily lock workflow. Live before the Thu 8 Oct 04:41 UTC run. | Claude, after Phase 1 approval |

### Facts still unverified
- The `HxG` provider and whether it includes penalties.
- What counts as "activity" for GitHub's 60-day scheduled-workflow rule.
- GitHub Pages speed from Juba (Phase 6).

## History
- 23 Sep 2026, session 1: PRD written with 26 open questions; approved.
- 23 Sep 2026, session 2: Phase 0 data audit. Understat and FPL barred; openfootball added; 72 mapping tests.
