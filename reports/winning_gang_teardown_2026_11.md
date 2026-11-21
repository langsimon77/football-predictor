# Winning Gang Betting Tips: how the tips and VIP tips are made

Date: 21 Nov 2026. App `com.gangbettingtips.winninggangfootballbettingtips` 2.0.16 (29),
file `apk/wg29.apk`, SHA-256 `319e7889be21bb951d3f21f16f11510200304b4a0cf4f61d2df022e04d4948ba`
(REA `open_binary` confirmed the same hash). Developer: Aslan Developer, the same name as
the Winner Expert app.

This updates `EVIDENCE.md` (20 Nov). That file covered only the basketball screen. The
football, Premium, Super Premium and tennis screens hide their strings with an encryption
layer, so their server addresses were missed. They are decoded here.

## Short answer

The app makes no predictions. Every tip, free or VIP, is a finished text row downloaded
from the developer's PHP server. VIP is a set of Google Play subscriptions that unlock
more server lists; the server checks the purchase. How the server picks tips is not in
the app. [Verified, static code]

## 1. Encrypted strings, decoded

Most app strings go through `S0/a.a(long)`, which calls `S0/b.b(long, String[])`. It
rebuilds each string from two scrambled 8,191-character blocks with a seeded random
generator (`S0/c.a`, `S0/c.c`). I ported it exactly (`tools/decode_strings.py`) and
decoded all 426 encrypted strings in the app classes (`evidence/decoded/strings.tsv`).
The port is checked: it produces valid web addresses, Play product names and JSON keys
that match the readable basketball screen.

## 2. Every tip list and who can see it

| Screen (class, method) | Server script | Who sees it |
|---|---|---|
| Football today (`MainActivity.D0`) | `mobil/show_bet.php` | free |
| Football last 15 (`MainActivity.D0`) | `mobil/show_oldbets.php` | free |
| High odds tips of the day (`MainActivity.F0`) | `mobil/show_highodds.php` | free (with ads) |
| Premium (`PremiumActivity.V`) | `mobil/show_premium_new.php` | subscription `winninggang_monthly` |
| Super Premium (`SuperPremiumActivity.W`) | `mobil/show_super.php` | subscription `winninggang_superfootball_monthly` |
| Basketball (`BasketballTipsActivity.N0`) | `show_basket.php`, `_old`, `_nba_new`, `_premium` | free; premium tab paid |
| Tennis (`TennisTipsActivity.N0`) | `show_tennis.php`, `_old`, `_premium` | free; premium tab `winninggang_tennis_monthly` |
| All paid screens | `gangbettingtips.com:3000/api/purchase_validator` | sends `token`, `sku`, `packageName` |

Every list request is a form POST with `version=29` and `key` (the app's signature
string, from the PiracyChecker library). Replies are decrypted with a key from the native
library (`CoreWrapper.generateNativeKey`), then read as JSON `bets`.

## 3. What each tip contains

| List | Fields read (all text) |
|---|---|
| Football free (`MainActivity.z0`) | `mac` match, `tahmin` pick, `saat` time, `oran` odds, `lig` league, `tahmindurumu` result |
| Premium (`PremiumActivity.U`) | `mac`, `tahmin`, `lig`, `saat`, `oran`, `durum`, **`yorum` (comment)** |
| Super Premium (`SuperPremiumActivity.V`) | `tarih` date, `lig`, `mac`, `tahmin`, `oran`, `durum` |
| Tennis (`TennisTipsActivity.K0`) | `tarih`, `turnuva`, `mac`, `tahmin`, `oran`, `durum` |

No list carries a probability, stake or confidence. The only VIP extra is `yorum`, a
written comment on Premium tips. Empty Premium shows "Premium tips are not added yet.
Please try again later!", which suggests a person adds them by hand. [Assumption, from
that message]

## 4. How VIP status works on the phone

`MainActivity` checks Google Play for `winninggang_monthly` and
`winninggang_superfootball_monthly`, sends the purchase token to the validator, and on
success stores `premium` / `super_premium` = true in the app's preferences ("Welcome to
Premium Club!"). It also counts rooted or tampered installs (`ispirated`, `violate_count`,
"Please Unroot your device"). None of this touches a tip's content.

## 5. What is absent

No maths in the decoded strings either: 0 matches for poisson, elo, probability, model,
expected. The app has no statistics library.

## Limits

- The server code is not available, so how tips are chosen (people, a model, copied) is
  unknown.
- Live replies were fetched on 20 Nov for basketball only (`http/`). Football and VIP
  replies were not fetched: they need a valid key or subscription, and I did not try.
- REA's own decompilers (JADX, Ghidra) are not set up on this Mac; REA confirmed the file,
  androguard read the code.

## What we built from it (tips_v2, 21 Nov 2026)

Lang's choices: extend the Tips tab; football and basketball; likeliest picks and value
picks shown separately; Gal odds when fresh; High Odds from 2.00; Super Premium shows all
value picks.

| Winning Gang | Ours | Source of the pick |
|---|---|---|
| Today's tips (free) | Free tips | best pick per game, Medium tier or better |
| Premium with comment (`yorum`) | Premium with a written reason | High tier; reason = our chance, expected goals or margin, tested win rate of that market and tier |
| Super Premium | Super Premium | every pick where our safe chance x Gal's price after 20% tax reaches 1.05 (the page's slip engine) |
| High odds tips of the day | High Odds tip of the day | best of those at Gal odds 2.00 or more |
| Basketball tips | Basketball winner picks | EuroLeague, NBL, ACB Elo forecasts, tiers bb_tiers_v1; NBL kept out of Diamond, Double and Treble (Lang) |
| Tennis | none | no tennis data |

Evidence: `reports/tips_backtest_2026_11.md`, `data/tips/market_record.json`,
`data/tips/basketball_tiers.json` (basketball High tier tested: won 80.1% of 592 games,
promised 81.2%; NBL alone 70.9% of 55, promised 78.9%, flagged on the page). Value tiers
have no track record yet: past Gal prices are not stored.
