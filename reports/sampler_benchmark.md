# Sampler benchmark (spec S5.1)

Run on GitHub's standard runner (Linux, 4 CPUs, Python 3.12.3) on 24 Sep 2026 by `.github/workflows/benchmark.yml`, workflow run 36058019513. Each fit is the full model as of the 8 Oct 2026 lock, through `fit_checked` (centred first, non-centred retry), 4 chains of 1,000 draws. Times include compilation, which the daily run also pays.

| League | Shots on target | Sampler | Seconds | Max R-hat | Min bulk ESS | Divergences | Retried | Passed |
|---|---|---|---|---|---|---|---|---|
| EPL | no | nutpie | 31.7 | 1.0045 | 1845 | 0 | yes | yes |
| EPL | no | NumPyro | 10.1 | 1.0085 | 542 | 0 | no | yes |
| EPL | yes | nutpie | 15.3 | 1.0040 | 1353 | 0 | no | yes |
| EPL | yes | NumPyro | 7.1 | 1.0049 | 1383 | 0 | no | yes |
| La Liga | no | nutpie | 19.3 | 1.0033 | 2146 | 0 | yes | yes |
| La Liga | no | NumPyro | 20.7 | 1.0031 | 2419 | 0 | yes | yes |
| La Liga | yes | nutpie | 11.9 | 1.0042 | 598 | 0 | no | yes |
| La Liga | yes | NumPyro | 7.4 | 1.0048 | 871 | 0 | no | yes |

**Decision:** NumPyro for the live model (shots-on-target variant), about twice as fast on the runner. Both samplers run NUTS on the same model, so the backtest, which used nutpie on the M1, is unaffected. An earlier run (36057104555) without the retry showed centred-only fits failing on goals-only La Liga with both samplers; that led to the retry design.
