# Betbook Betting Tips: how the tips and VIP tips are made

Date: 21 Nov 2026. App `com.betbook` 1.7.1 (20). Base APK
`~/Documents/Default Project/betbook-work/apk/com.betbook.apk`, SHA-256
`ba132a6ac47cb3d440c0c751903e53de8ecc7be85609993343596a36f41a945a` (REA `open_binary`
confirmed). Earlier analysis: `betbook-work/EVIDENCE.md` (20 to 21 Nov). The points below
were re-checked against the APK on 21 Nov with androguard and `strings`.

## Short answer

Betbook makes no predictions. Every tip, free or VIP, is a text row from one web API
(`bettingtips-api.azurewebsites.net`): teams, the tip as free text ("Bilbao Wins"), the
bookmaker odds, date, league and a result icon. VIP is the same kind of list under more
category names, unlocked by checking Google Play purchases on the phone only. [Verified]

## Evidence

| Claim | Where it is in the APK |
|---|---|
| One server | `ApiClient.getClient`: `https://bettingtips-api.azurewebsites.net/` |
| Four GET paths, one fixed app id | DEX strings: `/Mobile`, `/Mobile/WithPage`, `/Mobile/Rewards`, `/Mobile/WinnerCoupons`, each `?id=946012DA-2AFB-4DC8-B8CA-6895CFF361F0` |
| Every text field is encrypted with a key shipped in the app | `api.Security.Encrypt/Decrypt`: `AES/CBC/PKCS5Padding`, key `1BBE0E5E-4DAE-4B83-BF9A-C4029077B0BE` |
| 20 menu items: 8 VIP, 8 free, 4 offers | `entity.MenuItem.GetDataSource`: Elite, Fixed, Single+Double, Correct Score, HT-FT, Jack Pot, Daily 10+ Odds, Combine (VIP); Today's Top 3, Football Combine, Over-Under, Double Tips, Today's 20+ Odds, Single Game, Basketball, Tennis (free) |
| VIP decided on the phone | `MainActivity.showCategory` checks category names ("Elite VIP", "Correct", "HT-FT", "10+") against local purchase flags; SKUs `sku_elite_vip_month_1` and so on in `SubscriptionItem` |
| No model in the app | 0 matches for tensorflow, tflite, onnx, poisson, dixon, xgboost, expected goals, monte carlo across all three DEX files |

A tip object (`entity.Match`) has only Home, Visitor, scores, Bet (text), Rate (odds),
Status (an icon URL), Date, Time, League and Flag. No probability or confidence.

## What we could not see

- How the server picks tips. The 20 Nov notes say a day's Top 3 mixed sports and the
  history has hand-made entries, which points to people choosing them. [Assumption]
- The 20 Nov session also found the server returns VIP lists without any purchase check.
  That was not repeated on 21 Nov: it means reading paid content without paying.

## What we built (tips_v3, 21 Nov 2026)

Lang asked for six categories (the names come from the predictor-kit, built from Betbook
on 20 Nov), under the Tips tab, with these choices: merge with the existing tiers and
rename; VIP is a label, no lock; Correct Score shows the top 5; the basketball card shows
only forecasts that passed their tests.

| Category | Rule | Tested 2023/24 to 2025/26 (EPL, La Liga) |
|---|---|---|
| Today's Top 3 (free) | three likeliest picks of the day in Juba time, one per game, Medium tier or better | won 81.4% of 1,147, promised 82.2% |
| VIP Bankers | every game's strongest High-tier pick, no cap | won 80.4% of 1,625, promised 79.6% |
| VIP Full Card | up to two picks per game from different market families, Medium or better | won 77.7% of 4,560, promised 77.3% |
| VIP Correct Score | the five games whose likeliest exact score is most likely | won 15.1% of 1,604, promised 12.7% |
| VIP Accumulator | 3-fold and 4-fold from the strongest High picks, one per game, NBL kept out | 3-fold won 60.4% of 240 (promised 57.0%); 4-fold won 53.9% of 191 (promised 46.2%) |
| VIP Basketball | every game; winner, expected margin and total only where that market passed its test | winner High tier: won 80.1% of 592, promised 81.2% (data/tips/basketball_tiers.json) |

Correct Score and the 4-fold won more often than promised: the model is cautious there,
the safe direction. Basketball is not in the football backtest above. Diamond, Super
Premium and the High Odds tip stay from tips_v2.
