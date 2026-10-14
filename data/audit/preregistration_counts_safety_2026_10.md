# Pre-registration: corners and yellows, safety factor and referee update (14 Oct 2026)

Written before any of the analyses below was run. Lang asked to improve the corners and yellow-cards predictions "with a safety factor". No live forecast changes without Lang's approval.

## A. Safety factor for corners and yellows picks

- A pick is one side of a published line (corners over or under 8.5 to 11.5; yellows over or under 3.5 to 5.5), as on the Model Lab Predictions page.
- Its **safe chance** is the lower of (i) the model's chance and (ii) the lower end of a one-sided 90% Wilson interval for how often picks of the same kind (market family, five-point band of model chance) came true in the calibration seasons.
- Check S1 (does the safe chance stay safe on new seasons?): calibrate on 2021/22 and 2022/23, then on 2023/24 to 2025/26 compare, for every family and band with at least 30 test picks, the observed hit rate with the safe chance. Pass if the observed rate is at or above the safe chance in at least 90% of those cells [A: the interval is one-sided 90%].
- If S1 passes, the Model Lab shows the safe chance and "the lowest price with the safety margin" (break-even after Gal's 20% tax at the safe chance), calibrated on all five seasons. If it fails, nothing changes.

## B. EPL referee update for yellows

- The cards model uses the EPL referee only when the appointment is known at lock (Sunday, Monday and Thursday kickoffs). Appointments for the other matches reach football-data.co.uk on Friday or Tuesday afternoon, after the lock but before kickoff.
- Test: rerun the walk-forward cards backtest for the EPL, 2023/24 to 2025/26, twice on this Mac with the same code: as now, and with every referee known. Compare the log score of the total yellows on the same matches.
- Check R1: pass if the "referee known" minus "as now" difference has its 95% paired bootstrap interval (4,000 resamples) wholly below zero. If it passes, I propose an updated (not locked) yellows forecast once the referee is known, for Lang to approve. Locks never change.

## C. Which lines have skill

- For each corners and yellows line, log loss of the model's over probability against the league-average baseline (the Phase 3b baseline: a negative binomial matched to the league's last 380 results), on 2023/24 to 2025/26; EPL and La Liga pooled, and Serie A and Ligue 1 pooled.
- Report only. A line is marked "model better" when the interval of the difference lies wholly below zero, "no clear difference" otherwise.
