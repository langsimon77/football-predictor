# Pre-registration: basketball B6, forecast range widths (handicap and total points)

Date: 17 Nov 2026. Written and committed before any B6 model was fitted. Approved by Lang
("Approved all", 17 Nov 2026, for the five-step upgrade plan; this is step 1).

## 1. Why

B1 failed the NBL handicap on one check only: K2, the share of test games inside the 90% range,
was 84.9% against a floor of 86% [V: data/basketball/b1_results.json]. The accuracy check H1
passed. The range width (margin SD 14.06 points) was measured once on 252 tuning games and then
frozen [V: data/basketball/b1_settings.json]. The test errors imply about 15.0 [E: test mean
absolute error 11.95 / 0.798 for a bell curve]. The likely cause is a width that is too narrow
and cannot adapt, not a wrong expected margin.

## 2. What is tested

For each B1 league (EuroLeague, NBL) and each of the two range markets (handicap with the B1
margin model; total points with the B1 points model), these width methods:

| Code | Method |
|---|---|
| W0 | B1 as it is: fixed bell curve, width from the tuning seasons. |
| W1 | Bell curve whose width is the SD of the model's own errors over the last N games of the league, earlier days only. N in {100, 200, 400}. |
| W2 | Student-t curve (fatter tails) with the W1 rolling width, matched on variance (scale = SD x sqrt((df-2)/df)); df in {5, 10, 30}, with the same N grid. |

Rolling widths start with the W0 width until 60 earlier errors exist. Errors are measured on
games from the first warm-up season on, always from days before the game being forecast.

## 3. Choice (tuning seasons only)

`basketball/backtest_width.py tune` picks, per league and market, the method and settings with
the lowest mean CRPS on the B1 tuning seasons. W0 is kept unless another method is lower.
The choice is written to `data/basketball/b6_settings.json` and committed before any other step.

## 4. Scoring

1. **Seen seasons (descriptive only).** The B1 test seasons were already scored in B1 and seen
   by me in the diagnosis above, so scoring them again can describe but cannot confirm. B6 reports
   K2 coverage and CRPS against W0 for them, labelled as seen.
2. **Confirmation (decides live use).** The 2026/27 regular-season games, forecast before
   tip-off by the live run (locked in the ledger as a shadow column, never shown as the main
   forecast). After 100 recorded games per league (NBL expected around late January 2027 [E]),
   a market passes if both hold:
   - K2: 86% to 94% of games inside the chosen method's 90% range.
   - Its mean CRPS is not worse than W0's on the same games (bootstrap by game day, 95% upper
     bound of (chosen minus W0) below +0.10 points).
3. A market that passes goes live with the new widths. The NBL handicap goes live only through
   this route. No result can change these rules.

## 5. Out of scope

The expected margin and total (Elo, points model) are unchanged. ACB, LBA and ABA keep their B5
widths in this phase; if B6 passes, the same method is pre-registered for them separately.

## 6. Amendment 1 (17 Nov 2026, before any of these was fitted): steps 2 to 4

Same approval. All run as a shadow forecast (`ledger/basketball/shadow_b6.parquet`,
model `bb_b6_shadow`), locked at the same time as the main forecast, never shown as the main one.

- **Odds benchmark (step 2).** Prices from The Odds API (`basketball/odds.py`), last snapshot
  before tip-off. Reported per league once 100 locked games have a price: log loss of the
  main model's winner chance against the market's (margin removed), bootstrap by game day.
  This is a benchmark only; it changes nothing by itself.
- **Availability (step 3).** Point effects in `basketball/availability.py` are Assumptions.
  The shadow applies them. After 100 shadow games that have at least one entry, they pass if the
  margin CRPS with the effects is lower than without (95% upper bound of the difference below 0).
  If entries stay rare, this test waits; it is not run early.
- **Blend (step 4).** `basketball/blend.py`. The weight is fitted once on the first 150 locked
  games with a pre-tip-off price (per league), frozen and committed, then tested on the next 150:
  it passes if its winner log loss beats both the model alone and the market alone (95% upper
  bound below 0 for each). Only then does it replace the main forecast.
- **Step 5.** No new machine-learning challenger is added (B2 result).
