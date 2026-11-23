# Design: xG test in the model, xG panel and clean-up of the Model Lab page

Written 23 Nov 2026. Status: **waiting for Lang's approval.** Nothing here is built yet.

Labels: [V] verified (how), [E] estimate, [A] assumption, [C] Claude's call (Lang can overrule).

## 1. Intent

Lang asked to bring two pieces of work together:

- the Tips work (`handoff.md`: Tips tab, scorecard, Gal odds button), and
- the xG plan (`data/audit/preregistration_xg_2026_11.md`),

into one stronger model, show its results on the Model Lab page, and make that page
easier to read, easier to use and more clickable.

Agreed in the conversation on 23 Nov 2026:

- **Fair route.** xG does not go into the tips now. The two xG versions run hidden beside
  the live model until the verdict date (about 7 Jun 2027), as pre-registered. If one
  passes, Lang decides whether it replaces the live model, and from then on the tips use it.
  That is how the two pieces "merge": the Tips feed on whichever model has been shown to
  be better.
- **Approach A**: three small pieces, one after another (section 4).
- **The panel shows the match count and the average change only** before the verdict
  date. The pass or fail interval stays hidden until then.

## 2. Goals, non-goals, anti-goals

Goals

- G1. The two xG arms (`dc_bayes_xg_joint_v1`, `dc_bayes_xg_blend_v1`) built and scored
  exactly as the pre-registration says (part A walk-forward, part B daily shadow rows).
- G2. An "xG test" panel in the Model lab tab that Lang can read in 10 seconds.
- G3. The live page easier to read and use on a phone, with nothing that works today lost.

Non-goals

- No change to the published forecast, the tips, the stakes or the slips.
- No new data source (Understat stays barred).
- No rebuild of the page from scratch.

Anti-goals (a failure even if it "works")

- The panel shows anything that reads as a verdict before the end date: a pass or fail
  word, an interval, a coloured "winning" badge, or a sign test.
- Any rule in the pre-registration changed after seeing data.
- The page overwritten from the football-lab source (the live page is ahead of it).
- A feature on the live page stops working (slip checker, screenshot reader, bet history,
  Gal odds button, scorecard).

## 3. Constraints

- Live page: https://claude.ai/artifact/Kt9foBMJQ9uy1nbDohAFhH, about 6,600 lines, 47
  published files [V, Artifact read 23 Nov]. Changes go in as patch scripts in
  `~/Downloads/Football/football-lab/tools/merge_live/`, applied to the LIVE page, like
  `patch_tips_v4.py` and `patch_odds_button.py`.
- Page data reaches the page as `data/*.json`. The daily GitHub job writes them to branch
  `lab-data` [V, `.github/workflows/daily.yml` lines 175 to 194]; a Claude routine publishes
  them to the page.
- Every fit passes the usual gate (R-hat < 1.01, bulk ESS > 400, no divergences).
- Shadows never block the published forecast [V, `src/fp/pipeline/daily.py` line 490].
- Page text has no em or en dashes [V, `scripts/model_lab_refresh.py` BANNED].
- Lang merges every branch. CI must pass first (PR #36 lesson).
- Lang's rule: ask when unsure, never guess.

## 4. Approaches considered

| | Approach | Trade-off | Chosen? |
|---|---|---|---|
| A | Three small pieces in order: xG engine, xG panel, page clean-up patch | Slower "new look", nothing breaks | **Yes (Lang, 23 Nov)** |
| B | Rebuild the whole page, then add the panel | Cleaner code; risks losing features; 3 to 4 times the work | No |
| C | Put xG straight into the live model and tips | Fast; spoils the fair test, so we never learn whether xG helps | No (breaks the pre-registration) |

## 5. The design

### Piece 1: xG engine (football-predictor repo, branch from `xg-plan`)

Exactly build steps 1 to 3 of the pre-registration, section 9. Nothing added.

1. `src/fp/models/bayes_dc.py`: `xg_mode` in `BayesParams` and `build_model`
   (`none`, `joint`, `blend`). Tests first:
   - `xg_mode="none"` gives the same model and log-likelihood as today.
   - With xG missing everywhere, both xG modes equal today's model.
2. `src/fp/evaluate/backtest_bayes.py`: `--xg`. Run part A on GitHub (`backtest.yml`).
3. `src/fp/pipeline/daily.py` and `shadows`: lock both arms as shadow rows, never
   published. `scripts/check_ledger.py` still passes.
4. **All four leagues**, as the pre-registration says. Serie A and Ligue 1 are trial
   leagues: they lock through `src/fp/pipeline/trial.py` into `ledger/trial/` [V, 23 Nov].
   So `trial.py` and its ledger checks get the same two shadow rows, and the control there
   is the trial ledger's own `dc_bayes_v1_noshape` row [V, `trial.py` line 8].
5. Part A runs `backtest.yml` with `leagues: "EPL LaLiga SerieA Ligue1"` (the default is
   only `EPL LaLiga` [V]). [C]

**Where part A results live.** GitHub keeps run artifacts for 90 days only, and the verdict
is in June 2027. So part A's per-match results are committed to
`data/backtests/xg_2026_27/part_a.parquet` (one row per match and arm). [C]

**Part A and part B never overlap.** Part B starts on the day the shadows switch on
(pre-registration section 3). Rule: a match is in part B if its shadow rows were locked in
the ledger; otherwise it is in part A. Each match is counted once. The switch-on date is
written in `data/backtests/xg_2026_27/README.md` at merge time. [C]

Estimate: about 4 to 5 hours of work plus about 1 hour of runner time [E].

### Piece 2: xG test data file and panel

**Data file** `xg_test.json`, written by a new `scripts/make_xg_test.py` in the daily job
and copied to `lab-data` the same way as `tips.json` (daily.yml line 188). [C]

```
{
  "as_of": "2026-11-24T07:30Z",
  "end_date": "2027-06-07",
  "arms": {
    "dc_bayes_xg_joint_v1": {"n": 412, "mean_change": -0.0021,
                              "by_league": {"EPL": {"n": 100, "mean_change": ...}, ...},
                              "dropped": 3},
    "dc_bayes_xg_blend_v1": { ... }
  },
  "parts": {"A": {"n": 450, "mean_change": {"joint": ..., "blend": ...}},
            "B": {"n": 0,   "mean_change": {"joint": null, "blend": null}}},
  "fits": {"last_run_utc": "...", "joint_ok": true, "blend_ok": true}
}
```

- `mean_change` = xG arm log loss minus control log loss, per match, averaged
  (negative = xG better). Paired: a match counts only if both arms and the control have it.
- **No interval, no bootstrap, no pass/fail field in this file before the end date.** [C]
  The file cannot leak what it does not hold.
- After the end date, `reports/xg_test_2026_27.md` gives the verdict (pre-registration
  step 4); the panel then links to it.

**Panel** in the Model lab tab, at the top. Text sketch:

```
xG TEST                                    Verdict on 7 Jun 2027 (196 days)
Does adding expected goals make the forecasts better?  Hidden test, tips unchanged.

  Matches scored  1,032 of about 1,390   [##########------]

  Joint xG    average change  -0.0021   (minus = better than today's model)
  Blend xG    average change  +0.0008

  [ All leagues | EPL | La Liga | Serie A | Ligue 1 ]   [ Part A | Part B | Both ]

  Last fit: 24 Nov, both versions passed the fit checks.
  > What is this test?  (fold-out, plain words from the pre-registration)
  > Why no "winner" yet? (fold-out: one season can only show a gain of 0.003 to 0.007;
    looking early and stopping makes the test unfair)
```

- Both averages in the same neutral colour. No green or red. [C]
- League and part buttons are filters, not new numbers.
- If the file is missing: "The xG test has not started yet. It starts after the xG
  engine is merged." No error.
- `make_xg_test.py` reads both ledgers (`ledger/` and `ledger/trial/`) plus the part A file.
- The monthly review gets the same one-line progress note (matches scored, average change
  per arm), as pre-registration section 8 asks. No verdict in it.

Estimate: about 1.5 hours [E].

### Piece 3: page clean-up patch (`patch_readable_v1.py`)

A patch on the live page. Keeps every feature. [C] on each item, in priority order:

1. **Today: one-screen summary at the top.** Three tiles: "Best pick now", "Games
   today", "Odds updated" (reuses the Gal odds button). "Best pick now" = pick number 1
   in Today's Top 3 from `tips.json`. Each tile taps through to its tab.
2. **Bigger, calmer text.** Body 15 to 16 px, card titles stay large, captions 13 to 14 px,
   more space between cards on phones.
3. **Games: search and filters.** A search box (team name) and league chips above the
   list; filters remembered per viewer (browser storage, safe if it fails).
4. **Cards fold open on tap.** Long cards show one line (teams, pick, chance); tap to see
   the rest. "Open all / close all" button per section.
5. **Help in place.** Short "?" fold-outs next to hard words (log loss, value, banker),
   reusing the existing glossary.

Checked in the browser at phone and desktop width, light and dark, before publishing.
Estimate: about 3 hours [E].

## 6. Order and hand-offs

1. Piece 1 on a branch, PR, CI green, **Lang merges**.
2. Part A run on GitHub. Piece 2 data script in the same or a follow-up PR.
3. Piece 2 panel patch, published to the live page.
4. Piece 3 patch, published to the live page.

Each step stops for Lang where the pre-registration or the repo rules say so.

## 7. Left to the builder

- Function names, test names, file layout inside the patch scripts.
- Exact CSS values, as long as section 5 piece 3 holds and text stays readable in both
  themes.
- How `make_xg_test.py` reads the ledger (reuse what `make_tips.py` does where possible).

## 8. Open points to check before building (not guesses)

- Whether the 08:30 page routine publishes every JSON on `lab-data` or a fixed list. If
  fixed, `xg_test.json` needs adding to it (a routine change, so Lang's yes first).
