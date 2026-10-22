# Europe pipeline (Europa League and Conference League)

Written in a temporary folder on 22 Oct 2026, added to the repository on the lab-audit branch.
Forecasts for the two competitions the main pipeline does not cover, for the Model Lab.

## Steps (`make euro` runs the daily ones)

| Step | Script | Writes |
|---|---|---|
| Download the four free sources | `fetch_sources.py` | `data/raw/euro_sources/` (outside Git) |
| Merge them into one results table | `build.py` | `data/interim/euro/raw.pkl` |
| Resolve club names across sources | `prepare.py` (`names.py`, `data.py`) | `data/interim/euro/df.pkl` |
| Forecast the coming fixtures | `predict.py` (`elo.py`, `dc.py`, `link.py`) | `data/euro/pred.json` |
| Export for the Model Lab, with the lock rule | `export.py` | `data/euro/euro_gameweek.json`, `data/euro/history_seed.json` |

Monthly or on request (`make euro-backtest`): `bt.py` (walk-forward backtest, one setting per
run), `evalbt.py` (log loss by setting and blend weight), `evalx.py` (thin-data split),
`rec.py` (track record and safety margins: `data/euro/eurrec.json`).

## Sources (all free)

openfootball/europe, openfootball/football.json, openfootball/champions-league (CC0) and
xgabora/Club-Football-Match-Data (MIT). 2026/27 European fixtures and results: `euro2627.py`
(typed in from public reports on 22 Oct 2026; task 5.2 replaces it).

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
