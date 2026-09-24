# Model Changelog

Every change to model structure, features, or code that affects predictions is proposed here first and waits for Lang's approval (spec S0). Parameter and weight updates made automatically by the daily run are not listed here; they are logged by the run.

| Version | Date | Status | Change | Evidence |
|---|---|---|---|---|
| `dc_mle_v0` | 24 Sep 2026 | **Live** (Phase 1F approved 24 Sep 2026) | Dixon-Coles by weighted maximum likelihood. Decay 0.002 per day, ridge 10, promoted-team prior (attack −0.21, defence +0.14). Locks 1X2 and goals markets. | `reports/backtest_1f.md`: RPS 0.197 on 2023/24 to 2025/26; beats base rates, level with Elo, 0.006 behind the sharp closing market. |
| `elo_v0` | 24 Sep 2026 | **Live** as benchmark | Goal-difference Elo, K 10, home 60, carry 0.75, ordered-logit probabilities. Locks 1X2 only. | Same report: RPS 0.198. |
| Bayesian Dixon-Coles | Phase 2 | Planned | Replaces `dc_mle_v0` as the primary model once it passes Phase 2 checks. | |
