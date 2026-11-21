# How Winner Expert Betting Tips makes its predictions

Date: 21 Nov 2026. App: `com.aslanmuzaffer.winnerexpertbettingtips`, version 1.33 (code 38).
File: `~/Documents/Default Project/winner-work/apk/we38.apk`,
SHA-256 `687790a7b8a88e2e905ac9b00f089721dd479153e0420babf54c470c4a6a447f`.

## Short answer

The app does not compute any prediction. It has no model, no statistics and no odds
maths inside it. It downloads a ready-made list of tips from the developer's web server
(`winnerchoices.com`) and shows it. The VIP tiers are the same kind of list from
different server addresses, unlocked by a paid subscription. How the tips on the server
are chosen cannot be seen from the app. [Verified, static code below]

## Evidence

Tools: REA (`open_binary`, `inspect_artifact`) confirmed the file and its 2,929 entries.
REA's Java decompilers (JADX, Ghidra) are not installed on this Mac, so the code was read
with androguard (Dalvik bytecode dumps in `winner-work/evidence/dump/`). The code is
obfuscated with junk strings; only the readable strings and calls are quoted here.

### 1. Every tip list comes from a server address

All web addresses in the app code (`strings classes*.dex`):

| Address | Used for |
|---|---|
| `winnerchoices.com/mobil/select_expert_tips.php` | Free daily tips |
| `winnerchoices.com/mobil/show_expert_old.php` | Past tips (history) |
| `winnerchoices.com/mobil/show_expert_combo.php` | Free combo |
| `winnerchoices.com/mobil/show_expert_premium2.php` | VIP Premium (class `d`) |
| `winnerchoices.com/mobil/show_expert_coupons2.php` | VIP Double/Treble coupons (class `c`) |
| `winnerchoices.com/mobil/show_expert_diamond2.php` | VIP Diamond (class `b`) |
| `winnerchoices.com/mobil/push/register.php` | Push notification sign-up |

### 2. The app sends a form and gets back a JSON list

Class `b` (Diamond), `b_net.txt` lines 598 to 625: an OkHttp form with fields `id`, `v`
(= `"38"`, the app version), `i`, `m`, `d`, posted to `show_expert_diamond2.php`.
Classes `c` and `d` do the same for coupons and premium.

The reply is parsed with `JSONObject.getJSONArray("bets")`, after checking `"status"`.
Each tip has six text fields (Turkish names):

| Field | Meaning |
|---|---|
| `mac` | match (teams) |
| `tahmin` | prediction (the pick) |
| `saat` | kick-off time |
| `oran` | odds |
| `lig` | league |
| `tahmindurumu` | prediction status (won, lost, waiting) |

Every field is read with `getString` and put straight into a list for display. No field
is used in any calculation. [Verified, `a_v2.txt`, `b_net.txt`, `c_net.txt`, `d_net.txt`]

### 3. VIP is a subscription check, not a better model

`MainActivity.onCreate` (`main_oncreate.txt` lines 126 to 152) asks RevenueCat for the
user's entitlements `"premium"`, `"doubletreble"` and `"diamond"`
(`EntitlementInfos.get(...)`, `EntitlementInfo.isActive`), and stores them as
`premium`, `dt` and `dia` in SharedPreferences (lines 1328 to 1341). These flags only
decide which tabs open. [Verified]

### 4. What we could not see

- How the server picks tips, and whether the won/lost status is honest. That logic is in
  the PHP scripts, not in the app. The live feed was not fetched (permission refused in
  this session), so no real tips were inspected. [Unknown]
- What `i`, `m` and `d` contain (likely device or language values). [Assumption]

## What we built instead

Our version picks tips from our own locked forecasts and shows the track record
openly, which the app cannot prove. Code: `src/fp/tips/picks.py`,
`scripts/make_tips.py` (live), `scripts/backtest_tips.py` (record),
`tests/test_tips.py`. Results: `reports/tips_backtest_2026_11.md`.

| App product | Our rule |
|---|---|
| Free tips | Best pick of each match, Medium tier or better |
| Premium | High-tier picks only, top 5 of the day by probability |
| Double / Treble | The 2 or 3 strongest High picks from different matches; probability = product |
| Diamond | The strongest High pick with fair odds of at least 1.25 |
| Status | Won, lost or pending from `ledger/results.parquet` |
| Odds (`oran`) | Fair odds = 1 / probability (we have no free live bookmaker odds) |
