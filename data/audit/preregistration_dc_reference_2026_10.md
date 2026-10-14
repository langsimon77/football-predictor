# Pre-registration: reference Dixon-Coles and a blend (14 Oct 2026)

Written before any reference Dixon-Coles forecast was made. Lang asked for a fair comparison of the existing model, the reference Dixon-Coles model (MLGonzo/football_stats, adapted as `fp.models.dc_reference`), and a probability blend, keeping the blend only if it beats the existing model on validation and holds up on a final test period.

## Data and periods

- EPL and La Liga matches in `data/processed/matches.parquet`; walk-forward, each match predicted at its lock time from results known by then.
- Validation: 2021/22 and 2022/23 (all choices below are made here only).
- Test: 2023/24, 2024/25 and 2025/26, run once after the settings are fixed in `data/audit/dc_reference_settings.json`. The script refuses to run the test before the settings exist, or if this file changed after they were fixed.

## Models

- Existing: `dc_bayes_v1` with `shape_v1` (the published forecast), from its stored walk-forward forecasts.
- `dc_ref`: refitted at every lock on the previous 1,100 days. It has no forecast when a club has no match in that window (for example a newly promoted club before its first match); those matches are counted, and the existing forecast is used in their place wherever all matches are scored.
- Blend: weight × existing + (1 − weight) × dc_ref.
- `dc_mle_v0` (the project's own Dixon-Coles) is reported for context only.

## Choices on validation

1. Decay xi from {0, 0.0009, 0.0018, 0.0036}: lowest dc_ref log loss on the validation matches it covers.
2. Blend weight from 0, 0.05, ..., 1: lowest validation log loss over all validation matches. A weight of 1 means the blend is the existing model and there is nothing to test.
3. No calibration map is fitted (the project applies none without Lang's approval).

## Test rule

Keep the blend as an option only if, on the test seasons over all matches, the blend minus existing log loss has its 95% paired bootstrap interval (4,000 resamples) wholly below zero, and its mean Brier difference is not above zero. Otherwise the existing model stays alone and the blend is not offered. Either way, nothing changes in the daily run without Lang's approval.

Reported, not judged: dc_ref alone against the existing model, accuracy, ranked probability score, calibration slope and expected calibration error, results by season, and the share of matches dc_ref cannot forecast.
