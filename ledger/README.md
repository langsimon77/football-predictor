# Prediction ledger

The daily run writes two files here.

| File | Contents | Rules |
|---|---|---|
| `predictions.parquet` | One row per locked prediction per model: match, kickoff, lock time, model version (Git commit), every probability, flags. | Append-only. Each row carries a SHA-256 hash chained to the previous row. CI fails if any old row changes or disappears. |
| `results.parquet` | The outcome of every locked match that has been played. | Rebuilt each run from the sources, so a corrected score is picked up. |

The Git history of `predictions.parquet` shows when each prediction was committed, which proves it existed before kickoff.

Read the files with `pandas.read_parquet`, or query them from `data/processed/football.duckdb` after `make data`.
