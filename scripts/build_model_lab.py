"""Build the Model Lab artifact: one self-contained HTML page with every analysis.

The page is a snapshot: the data is embedded, so it opens instantly and works
offline. Rerun this script to refresh it, then republish the same file.

    uv run python scripts/build_model_lab.py OUT.html [--pages-dir DIR]

--pages-dir: a folder holding the published dashboard files (fixtures.parquet,
details.parquet, meta.json) downloaded from the GitHub Pages site.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from fp import ROOT
from fp.ensemble import stacking
from fp.evaluate import metrics
from fp.features import ml_features
from fp.ingest.matches import PROCESSED
from fp.models.priors import PromotedPrior
from fp.models.promotion import fit_promotion_model
from fp.pipeline import daily
from fp.teams import teams
from fp.validate.leakage import known_as_of

sys.path.insert(0, str(Path(__file__).parent))
import stack_steadiness  # noqa: E402

TEMPLATE = ROOT / "tools" / "model_lab" / "template.html"
BACKTESTS = ROOT / "data" / "backtests"
MODELS_1X2 = ["bdc", "elo", "dc", "multinomial", "ordered_logit", "random_forest", "xgboost",
              "base", "mkt_pre", "mkt_sharp"]
LINES = {"goals": [1.5, 2.5, 3.5], "corners": [8.5, 9.5, 10.5, 11.5], "yellows": [3.5, 4.5, 5.5]}
SIM_DRAWS = 500


def milli(x: np.ndarray) -> list[int]:
    """Probabilities as whole thousandths (-1 for missing): compact JSON."""
    a = np.asarray(x, dtype=float)
    return [int(v) if v >= 0 else -1 for v in np.where(np.isfinite(a), np.round(a * 1000), -1)]


def demargin(frame: pd.DataFrame, cols: list[str]) -> np.ndarray:
    if not set(cols) <= set(frame.columns):
        return np.full((len(frame), len(cols)), np.nan)
    return metrics.demargin_power(frame[cols].to_numpy(dtype=float))


def base_rates(matches: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """League base rates at each lock (previous 1,100 days) for every line."""
    out = []
    for (league, lock), group in frame.groupby(["league", "lock_utc"]):
        known = known_as_of(matches[matches["league"] == league], pd.Timestamp(lock))
        recent = known[known["kickoff_utc"] >= pd.Timestamp(lock) - pd.Timedelta(days=1100)]
        goals = recent["home_goals"] + recent["away_goals"]
        corners = (recent["home_corners"] + recent["away_corners"]).dropna()
        yellows = (recent["home_yellows"] + recent["away_yellows"]).dropna()
        row = {"base_btts": float(((recent["home_goals"] > 0) & (recent["away_goals"] > 0)).mean())}
        for line in LINES["goals"]:
            row[f"base_goals_{line}"] = float((goals > line).mean())
        for line in LINES["corners"]:
            row[f"base_corners_{line}"] = float((corners > line).mean())
        for line in LINES["yellows"]:
            row[f"base_yellows_{line}"] = float((yellows > line).mean())
        out.append(pd.DataFrame([row] * len(group)).assign(match_id=group["match_id"].to_numpy()))
    return pd.concat(out, ignore_index=True)


def backtest_block(matches: pd.DataFrame, names: dict[str, int]) -> dict:
    b = pd.read_parquet(BACKTESTS / "baselines_2021_2025.parquet")
    b = b.sort_values("kickoff_utc").reset_index(drop=True)
    m = matches.set_index("match_id")
    b["home_id"] = b["match_id"].map(m["home_id"])
    b["away_id"] = b["match_id"].map(m["away_id"])
    b["reds"] = b["match_id"].map(m["home_reds"].fillna(0) + m["away_reds"].fillna(0))
    odds = m.reindex(b["match_id"])
    pre = demargin(odds, ["odds_avg_pre_home", "odds_avg_pre_draw", "odds_avg_pre_away"])
    pin = demargin(odds, ["odds_pin_close_home", "odds_pin_close_draw", "odds_pin_close_away"])
    bfe = demargin(odds, ["odds_bfe_close_home", "odds_bfe_close_draw", "odds_bfe_close_away"])
    sharp = np.where(np.isfinite(pin), pin, bfe)
    pre_ou = demargin(odds, ["odds_avg_pre_over25", "odds_avg_pre_under25"])[:, 0]
    pin_ou = demargin(odds, ["odds_pin_close_over25", "odds_pin_close_under25"])[:, 0]
    bfe_ou = demargin(odds, ["odds_bfe_close_over25", "odds_bfe_close_under25"])[:, 0]
    sharp_ou = np.where(np.isfinite(pin_ou), pin_ou, bfe_ou)

    bdc = pd.read_parquet(BACKTESTS / "dc_bayes_v1_walkforward_2021_2025.parquet").set_index(
        "match_id").reindex(b["match_id"])
    mats = np.stack([np.asarray(x, dtype=float).reshape(11, 11) for x in bdc["bdc_matrix"]])
    total = np.add.outer(np.arange(11), np.arange(11))
    iv = bdc["bdc_intervals"].map(json.loads)
    corners = pd.read_parquet(BACKTESTS / "corners_total_poisson_walkforward_2021_2025.parquet"
                              ).set_index("match_id").reindex(b["match_id"])
    cards = pd.read_parquet(BACKTESTS / "cards_nb_walkforward_2021_2025.parquet"
                            ).set_index("match_id").reindex(b["match_id"])
    base = base_rates(matches, b[["match_id", "league", "lock_utc"]]).set_index(
        "match_id").reindex(b["match_id"])

    sched = ml_features.schedule(matches, b.assign(lock_utc=b["lock_utc"]))
    promoted = ml_features.promoted_teams(matches)
    early = np.zeros(len(b), dtype=bool)
    for side in ("home", "away"):
        is_p = np.array([promoted.get((t, int(s)), 0) == 1
                         for t, s in zip(b[f"{side}_id"], b["season"], strict=True)])
        played = b["match_id"].map(sched[f"played_{side}"]).to_numpy()
        early |= is_p & (played < 6)

    one = {}
    src = {"bdc": "p", "base": "base"}
    for mname in MODELS_1X2:
        if mname == "mkt_pre":
            arr = pre
        elif mname == "mkt_sharp":
            arr = sharp
        else:
            prefix = src.get(mname, mname)
            arr = b[[f"{prefix}_{k}" for k in ("home", "draw", "away")]].to_numpy(float)
        one[mname] = milli(arr.ravel())
    binary: dict[str, list[int]] = {}
    for line in LINES["goals"]:
        binary[f"bdc_goals_{line}"] = milli(mats[:, total > line].sum(axis=1))
        binary[f"base_goals_{line}"] = milli(base[f"base_goals_{line}"])
    binary["bdc_btts"] = milli(mats[:, 1:, 1:].sum(axis=(1, 2)))
    binary["base_btts"] = milli(base["base_btts"])
    binary["mkt_pre_goals_2.5"] = milli(pre_ou)
    binary["mkt_sharp_goals_2.5"] = milli(sharp_ou)
    for line in LINES["corners"]:
        binary[f"model_corners_{line}"] = milli(corners[f"p_over_{str(line).replace('.', '_')}"])
        binary[f"base_corners_{line}"] = milli(base[f"base_corners_{line}"])
    for line in LINES["yellows"]:
        binary[f"model_yellows_{line}"] = milli(cards[f"p_over_{str(line).replace('.', '_')}"])
        binary[f"base_yellows_{line}"] = milli(base[f"base_yellows_{line}"])

    def width(key: str) -> list[int]:
        return milli(np.array([d[key][1] - d[key][0] for d in iv]))

    return {
        "n": len(b), "id": b["match_id"].tolist(),
        "lg": (b["league"] == "LaLiga").astype(int).tolist(),
        "ss": b["season"].astype(int).tolist(),
        "date": pd.to_datetime(b["kickoff_utc"], utc=True).dt.strftime("%Y-%m-%d").tolist(),
        "h": b["home_id"].map(names).tolist(), "a": b["away_id"].map(names).tolist(),
        "hg": b["home_goals"].astype(int).tolist(), "ag": b["away_goals"].astype(int).tolist(),
        "cor": (b["home_corners"] + b["away_corners"]).fillna(-1).astype(int).tolist(),
        "yel": (b["home_yellows"] + b["away_yellows"]).fillna(-1).astype(int).tolist(),
        "reds": b["reds"].fillna(0).astype(int).tolist(),
        "y": b["outcome"].astype(int).tolist(),
        "p": one, "bin": binary,
        "wd": {"home": width("p_home"), "draw": width("p_draw"), "away": width("p_away"),
               "goals_2.5": width("p_over_2_5"), "goals_1.5": width("p_over_1_5"),
               "goals_3.5": width("p_over_3_5"), "btts": width("p_btts")},
        "promo": early.astype(int).tolist(),
        "refk": cards["referee_known"].fillna(False).astype(bool).astype(int).tolist(),
        "mx": [int(v) for v in np.round(mats[:, :7, :7].reshape(len(b), -1) * 1000).ravel()],
    }


def upcoming_block(pages: Path, names: dict[str, int]) -> dict:
    fx = pd.read_parquet(pages / "fixtures.parquet").sort_values("kickoff_utc")
    det = pd.read_parquet(pages / "details.parquet").set_index("match_id")
    rows = []
    for r in fx.itertuples():
        if r.match_id not in det.index:
            continue
        d = det.loc[r.match_id]
        mat = np.asarray(d["matrix"], dtype=float).reshape(11, 11)
        rows.append({
            "id": r.match_id, "lg": int(r.league == "LaLiga"), "h": names[r.home_id],
            "a": names[r.away_id], "kickoff": f"{pd.Timestamp(r.kickoff_utc):%Y-%m-%dT%H:%MZ}",
            "round": r.round, "locked": bool(r.locked),
            "p": milli([r.p_home, r.p_draw, r.p_away]),
            "goals": {k: float(np.round(v, 3)) for k, v in (
                ("exp_home", r.exp_goals_home), ("exp_away", r.exp_goals_away),
                ("over_1.5", r.p_over_1_5), ("over_2.5", r.p_over_2_5),
                ("over_3.5", r.p_over_3_5), ("btts", r.p_btts))},
            "corners": None if pd.isna(r.exp_corners_home) else
            round(float(r.exp_corners_home + r.exp_corners_away), 2),
            "yellows": None if pd.isna(r.exp_yellows) else round(float(r.exp_yellows), 2),
            "tiers": json.loads(r.tiers) if isinstance(r.tiers, str) else {},
            "intervals": json.loads(r.intervals) if isinstance(r.intervals, str) else {},
            "models": json.loads(d["models"]), "drivers": json.loads(d["drivers"]),
            "mx": [int(v) for v in np.round(mat[:7, :7] * 1000).ravel()],
            "cpmf": milli(np.asarray(d["corners_pmf"])[:21])
            if isinstance(d["corners_pmf"], (list, np.ndarray)) else None,
            "ypmf": milli(np.asarray(d["cards_pmf"])[:13])
            if isinstance(d["cards_pmf"], (list, np.ndarray)) else None,
        })
    return {"rows": rows, "meta": json.loads((pages / "meta.json").read_text())}


def simulator_block(matches: pd.DataFrame, fixtures: pd.DataFrame, names: dict[str, int],
                    now: pd.Timestamp) -> dict:
    second = pd.read_parquet(PROCESSED / "second_tier.parquet")
    prior = PromotedPrior(matches)
    promo = fit_promotion_model(matches, second)
    season = int(fixtures["season"].max())
    known = known_as_of(matches, now)
    out = {}
    with tempfile.TemporaryDirectory() as store:
        for league in ("EPL", "LaLiga"):
            lm = daily.fit_league(matches, fixtures, league, now, prior, season, second, promo,
                                  with_bayes=True, store=Path(store))
            post = lm.bayes
            assert post is not None
            fx = fixtures[fixtures["league"] == league]
            clubs = sorted(set(fx["home_id"]))
            idx = [post.index(c) for c in clubs]
            rng = np.random.default_rng(0)
            pick = rng.choice(len(post.mu), SIM_DRAWS, replace=False)
            played = known[(known["league"] == league) & (known["season"] == season)]
            extra = fx[fx["home_goals"].notna() & ~fx["match_id"].isin(played["match_id"])
                       & (fx["kickoff_utc"] < now)]
            done = set(played["match_id"]) | set(extra["match_id"])
            results = pd.concat([played[["home_id", "away_id", "home_goals", "away_goals"]],
                                 extra[["home_id", "away_id", "home_goals", "away_goals"]]])
            remaining = fx[~fx["match_id"].isin(done)]
            out[league] = {
                "clubs": [names[c] for c in clubs],
                "mu": [round(float(v), 4) for v in post.mu[pick]],
                "home": [round(float(v), 4) for v in post.home[pick]],
                "att": [round(float(v), 4) for v in post.att[np.ix_(pick, idx)].ravel()],
                "def": [round(float(v), 4) for v in post.def_[np.ix_(pick, idx)].ravel()],
                "results": [[names[h], names[a], int(x), int(y)] for h, a, x, y in
                            results.itertuples(index=False)],
                "remaining": [[names[h], names[a]] for h, a in
                              zip(remaining["home_id"], remaining["away_id"], strict=True)],
                "diagnostics": {k: (round(float(v), 4) if isinstance(v, float) else v)
                                for k, v in post.diagnostics.items()},
            }
    return out


def evidence_block() -> dict:
    cv = pd.read_parquet(BACKTESTS / "challengers_walkforward_2021_2025_cv.parquet")
    stack = json.loads((ROOT / "data" / "stacking" / "stack_1x2.json").read_text())
    tiers = json.loads((ROOT / "data" / "tiers" / "thresholds.json").read_text())
    base = pd.read_parquet(BACKTESTS / "baselines_2021_2025.parquet")
    y = base["outcome"].to_numpy(int)
    per_season = {}
    for yr in (2021, 2022):
        sel = (base["season"] == yr).to_numpy()
        w = stacking.fit({mm: stack_steadiness.component(base[sel], mm)
                          for mm in stack_steadiness.MODELS}, y[sel]).weights
        per_season[str(yr)] = dict(zip(stack_steadiness.MODELS, np.round(w, 4).tolist(),
                                       strict=True))
    # The steadiness replay (reports/stack_steadiness.md): weekly weight paths.
    frame = base.copy()
    m = pd.read_parquet(PROCESSED / "matches.parquet").set_index("match_id")
    frame["result_available_utc"] = frame["match_id"].map(m["result_available_utc"])
    frame["kickoff_utc"] = pd.to_datetime(frame["kickoff_utc"], utc=True)
    frame["lock_utc"] = pd.to_datetime(frame["lock_utc"], utc=True)
    frame = frame.sort_values("lock_utc").reset_index(drop=True)
    start = np.asarray(stack["weights"], dtype=float)
    _, h0 = stack_steadiness.replay(frame, [2023, 2024, 2025], start, 0.0)
    _, h1 = stack_steadiness.replay(frame, [2023, 2024, 2025], start, 0.1)
    paths = {"weeks": [f"{w:%Y-%m-%d}" for w in h0["week"]],
             "current": {mm: np.round(h0[f"w_{mm}"], 3).tolist()
                         for mm in stack_steadiness.MODELS},
             "steadier": {mm: np.round(h1[f"w_{mm}"], 3).tolist()
                          for mm in stack_steadiness.MODELS}}
    return {"cv": [{"model": r.model, "params": json.dumps(json.loads(r.params)),
                    "log_loss": round(float(r.log_loss), 5)} for r in cv.itertuples()],
            "stack": stack, "stack_by_season": per_season, "tiers": tiers,
            "steadiness": paths}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--pages-dir", type=Path, required=True)
    args = ap.parse_args(argv)
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    fixtures = pd.read_parquet(PROCESSED / "fixtures.parquet")
    club = teams()
    ids = sorted(set(matches["home_id"]) | set(fixtures["home_id"]))
    names = {t: i for i, t in enumerate(ids)}
    short = club.set_index("team_id")["short_name"].to_dict()
    meta = json.loads((args.pages_dir / "meta.json").read_text())
    now = pd.Timestamp(meta["generated_utc"])
    data = {
        "built": f"{pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC",
        "data_as_of": meta["generated_utc"], "model_version": meta["model_version"],
        "clubs": [short.get(t, t) for t in ids],
        "bt": backtest_block(matches, names),
        "up": upcoming_block(args.pages_dir, names),
        "sim": simulator_block(matches, fixtures, names, now),
        "ev": evidence_block(),
    }
    blob = json.dumps(data, separators=(",", ":"), allow_nan=False)
    page = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", blob)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print(f"wrote {args.out} ({len(page) / 1e6:.2f} MB, data {len(blob) / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    np.seterr(all="ignore")
    sys.exit(main())
