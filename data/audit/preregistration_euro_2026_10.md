# Pre-registration: Europe pipeline experiments (22 Oct 2026)

Written before any of these results was computed. Tasks 5.3 to 5.7 of the Model Lab audit.

## Data and split (unchanged from the pipeline's own test)

European matches of the three UEFA competitions from 1 Jul 2023 to 21 Oct 2026 (1,199),
every forecast made walk-forward: the models are refitted at the start of each month and
score that month's matches only. Tuning window: matches before 1 Jul 2025 (938). Hold-out:
from 1 Jul 2025 (261). Everything is chosen on the tuning window; the hold-out is used once.

Current model (the reference): goals model with half-life 365 days, penalty 0.0003, country
scale 3.0, Dixon-Coles rho fixed at -0.05; blended 0.8 goals model, 0.2 Elo. Log loss of home,
draw, away: 0.9393 on all 1,199, 0.9480 tuning, 0.9082 hold-out.

## Experiments

1. Goals model settings (5.3): half-life 180, 270, 365, 540 or 730 days, penalty 0.0001,
   0.0003 or 0.001, and rho fitted by maximum likelihood each month on the European matches
   before that month (instead of -0.05). Pick the best by tuning log loss.
2. Totals calibration (5.4): (a) a goals shift per competition (one number added to both
   teams' log scoring rates, fitted on the tuning window); (b) isotonic regression of the
   over 2.5 chance fitted on the tuning window. Metric: hold-out log loss of over 2.5.
3. Home, draw, away calibration (5.5): (a) temperature scaling, (b) Dirichlet calibration
   (multinomial logistic on the log chances), fitted on the tuning window.
4. Stacked blend (5.6): multinomial logistic on both models' log chances and each team's
   number of matches in the previous 365 days, fitted on the tuning window.
5. New teams (5.7): Elo start for a club not seen before from the goals model's league
   strength (instead of the country average minus 75). Metric: hold-out log loss on matches
   where either team had fewer than 15 matches in the previous 365 days, and on all.

## Decision rule

For each experiment, the hold-out log loss difference against the reference, with a paired
bootstrap 95% interval (2,000 resamples of the hold-out matches). A change is proposed only if
the whole interval is below zero after a Holm correction across the five experiments. A
smaller gain is reported as not shown. Nothing goes live without Lang's approval
(MODEL_CHANGELOG).
