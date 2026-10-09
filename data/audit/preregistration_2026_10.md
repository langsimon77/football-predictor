# Pre-registration: replication of the goals shape fix

Written 9 Oct 2026, 09:40 UTC, before the 2018/19 to 2020/21 forecasts were downloaded or looked at
(GitHub run 37909076802, published model `dc_bayes_v1`, shots on target, NumPyro, unchanged code).

Candidates (both found on 2021/22 to 2025/26, see `reports/audit_2026_10.md`):

1. **Stretch only**: the gap between the two scoring rates widened by s, with the Dixon-Coles rho,
   both fitted on 2021/22 and 2022/23 scorelines (s = 0.0904, rho = 0.0065).
2. **Stretch plus shape**: stretch s, home and away dispersion, and rho fitted on the latest 730 days
   of stored forecasts (what would go live today).

Replication seasons: 2018/19 and 2019/20 (both leagues). 2020/21 (no crowds) is reported separately
and does not count.

Rule: a candidate replicates if the whole 97.5% bootstrap interval (two candidates, Bonferroni) of its
change in home, draw, away log loss against the unchanged forecasts is below zero. Other markets are
reported, not judged. Known caveat: the promoted-club prior was estimated on 2017/18 to 2020/21, so
promoted clubs' base forecasts in these seasons are slightly too good; both arms share it.
