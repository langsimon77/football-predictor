# Europe pipeline (Europa League and Conference League)

Written in a temporary folder on 22 Oct 2026, added to the repository on the lab-audit branch.
Forecasts for the two competitions the main pipeline does not cover, for the Model Lab.

## Steps (`make euro` runs the daily ones)

| Step | Script | Writes |
|---|---|---|
| Download the four free sources | `fetch_sources.py` | `data/raw/euro_sources/` (outside Git) |
| Merge them into one results table | `build.py` | `data/interim/euro/raw.pkl` |
| Resolve club names, cross-check this season's fixtures | `prepare.py` (`names.py`, `data.py`, `fixtures.py`) | `data/interim/euro/df.pkl`, `fixtures.json`; `data/euro/fixtures_check.json` |
| Forecast the coming fixtures | `predict.py` (`elo.py`, `dc.py`, `link.py`) | `data/euro/pred.json` |
| Export for the Model Lab, with the lock rule | `export.py` | `data/euro/euro_gameweek.json`, `data/euro/history_seed.json` |

Monthly or on request (`make euro-backtest`): `bt.py` (walk-forward backtest, one setting per
run), `evalbt.py` (log loss by setting and blend weight), `evalx.py` (thin-data split),
`rec.py` (track record and safety margins: `data/euro/eurrec.json`).

## Sources (all free)

openfootball/europe, openfootball/football.json, openfootball/champions-league (CC0) and
xgabora/Club-Football-Match-Data (MIT). 2026/27 European fixtures and results come from two
sources, cross-checked by `fixtures.py` (run in `prepare.py`): Wikipedia's league-phase results
grids (MediaWiki API) and `euro2627.py` (typed in from public reports on 22 Oct 2026; it also
has kick-off times and the qualifying rounds). A fixture or result in both, agreeing, is
verified; anything else is flagged unverified on the Model Lab cards, and a result the sources
disagree on is left out of training. `data/euro/fixtures_check.json` reports the counts. No
free structured source has these two competitions otherwise: football-data.org's free tier
does not cover them and openfootball stops at 2025/26 (Champions League only).

## Settings

`final_cfg.json` (goals model: half-life, penalty, country scale, blend weight, rho) and
`elo_params.json`. `EURO_RUN_DATE` sets the run date (default today, UTC); results up to the
day before are used. `EURO_NOW` sets the clock for the lock rule (default now).

## Lock rule

`export.py` never rewrites a match whose kickoff has passed: its last forecast before kickoff
is carried over unchanged.

## What it cannot do

The daily GitHub run writes files only. The Model Lab's history documents live in the
artifact's database, which only Claude can write: the nightly settle task reads
`data/euro/history_seed.json` and upserts the documents.
