# Basketball B6: model upgrade (odds, availability, NBL handicap, blend)

Date: 17 Nov 2026. Branch `ccr-40baa957-wpn1q8`. Approval: Lang, "Approved all" (17 Nov 2026).
Rules fixed beforehand: `data/audit/preregistration_basketball_b6_width_2026_11.md`
(sections 1 to 5 in 2ab94eb, amendment 1 in fb19534, both before any fit; amendment 2 after).

Claim labels: **[V]** Verified, with source. **[E]** Estimate, with basis. **[A]** Assumption.

## 1. Verdict for Lang

| Step | Status | What it changes today |
|---|---|---|
| 1. NBL handicap fix | Adaptive width **did not win on tuning**; a 200-game rolling width is pre-registered and tested on live games | Nothing shown yet; shadow ledger collects the test |
| 2. Odds | Built; **needs the `ODDS_API_KEY` GitHub secret** | Prices stored from the next run after the secret is added |
| 3. Player availability | Built as a typed file; no permitted automatic source exists | Shadow forecast only |
| 4. Blend model and market | Built; weight fitted after 150 priced games per league | Nothing until then |
| 5. No complex ML | Kept (B2 result) | None |

**Nothing on the Model Lab changes until a pre-registered test passes.** All new work runs as a
second, locked "shadow" forecast (`ledger/basketball/shadow_b6.parquet`) next to the main one.

## 2. Step 1: NBL handicap

- **Data rebuilt** from Wikipedia on 17 Nov 2026; the B1 numbers reproduce exactly (NBL margin
  coverage 84.89%, EuroLeague 90.26%) [V: `data/basketball/b6_seen.json`].
- **Tuning** (B1 tuning seasons only) compared the fixed width (W0) with rolling widths (W1) and
  fat-tailed curves (W2). W0 had the lowest CRPS in all four league and market pairs; the best
  challenger was 0.005 to 0.006 points behind [V: `data/basketball/b6_settings.json`]. By the rule,
  W0 stays. Part of W0's edge is in-sample: its width was measured on those same seasons [E].
- **Seen seasons (exploratory, cannot decide):** a 200-game rolling width would have caught 88.9%
  of NBL margins (pass band 86% to 94%) with the same CRPS (8.546 against 8.547) [V: rerun].
- **So:** this is now amendment 2, tested on future games only. After 100 NBL games with results
  (around late January 2027 [E: about 8 NBL games a week]), the NBL handicap goes live with the
  rolling width if it passes, or with W0 if W0 passes on those games, or stays off.
- **NBL totals:** the recent error width is 19.1 points against the fixed 16.5 [V: shadow run,
  17 Nov 2026]. Totals have become more spread out, which is why that market failed. The same
  live test covers it.

## 3. Step 2: odds (`basketball/odds.py`)

- Source: The Odds API v4, EuroLeague (`basketball_euroleague`) and NBL (`basketball_nbl`)
  [A: sport keys to confirm on the first run]. ACB, LBA and ABA are not covered.
- Galsport was not used: its terms on automated access could not be found, and this environment
  cannot reach it [V: proxy refusal, 17 Nov 2026]. Typed Galsport prices remain possible (B0-D3).
- Cost control: one region, three markets (3 credits a call), a league is fetched only when it
  has a game within 36 hours and no snapshot in the last 10 hours [E: about 250 to 300 credits a
  month; the free plan's limit is Unverified].
- The key is read from the `ODDS_API_KEY` secret, sent only as the API's URL parameter, never logged.

## 4. Step 3: availability (`basketball/availability.py`)

- No free, machine-readable injury feed with clear terms: EuroLeague official data is barred
  (B0-D4); the NBL's injury list ([nbl.com.au](https://www.nbl.com.au/news/nbl26-the-latest-injury-updates))
  and [basketball.com.au's tracker](https://www.basketball.com.au/news/nbl-injury-report) are news pages.
- Lang (or a Claude routine) adds rows to `data/manual/basketball_availability.csv`:
  `league,date,club,player,role,status,source`. Effects [A]: star 3.0, starter 1.5, rotation 0.5
  points of margin; doubtful counts half; capped at 6.0 per team; half comes off the total.
- Tested once 100 shadow games carry entries.

## 5. Step 4: blend (`basketball/blend.py`)

Logarithmic pool of model and market winner chances; lines blended the same way. Weight fitted
once on the first 150 priced games per league, frozen, tested on the next 150. It replaces the
main forecast only if it beats both the model alone and the market alone.

## 6. Tracking

`uv run python basketball/b6_check.py` writes `reports/basketball_b6_progress.md`: games
collected, range coverage, and each test's verdict once its count is reached.

## 7. Open items

1. Lang: add `ODDS_API_KEY` as a GitHub Actions secret.
2. Confirm The Odds API sport keys and free-plan credits on the first live run.
3. Extend the width method to ACB, LBA and ABA only if B6 passes (separate pre-registration).
