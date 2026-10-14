# Pre-registration: safety margin for every pick (14 Oct 2026)

Written before this analysis was run. Lang asked for "a reasonable safety factor for all your predictions to act as a buffer". This extends the corners and yellows safety margin (`data/audit/preregistration_counts_safety_2026_10.md`, check S1 passed) to every pick family on the Model Lab: home, draw, away; double chance; European handicap; draw no bet; goal lines; both teams score; corners; yellows. Forecasts and locks do not change.

## Safe chance

Same rule as for corners and yellows: the lower of the model's chance and the lower end of a one-sided 90% Wilson interval for how often picks of the same family and five-point band came true. Draw no bet is judged on matches that were not drawn: the band and the record use the chance of winning given no draw, and the safe win chance is that safe conditional chance times the chance of no draw.

## Check, per family

Calibrate on 2021/22 and 2022/23 (EPL and La Liga), test on 2023/24 to 2025/26, cells with at least 30 test picks. A family passes if the observed hit rate is at or above the safe chance in at least 90% of its cells.

- A family that passes gets the 90% margin in the Model Lab.
- A family that fails is tested once more with a one-sided 95% interval; if that passes, it gets the 95% margin.
- A family that fails both keeps its plain price, marked "no reliable safety margin".

The published margins are then calibrated on all five seasons.

## Addendum, 14 Oct 2026: Serie A and Ligue 1

Written before this part was run. Lang asked to add Serie A and Ligue 1 to the predictions "using the same or better standards". Only the markets that passed their backtest are shown (`reports/trial_backtest_2026_10.md`): home, draw, away, with double chance and draw no bet (both come straight from those three numbers), and yellow cards. The same safety rule as above is applied to these four families, using the two leagues' own walk-forward forecasts (published goals forecast with the goals fix refitted on their own history; `cards_nb_v1` without referee): margins built on 2021/22 and 2022/23, checked on 2023/24 to 2025/26, 90% then 95%, else no margin and flagged. The track record shown ("came true in testing") is the two leagues' own, 2023/24 to 2025/26.
