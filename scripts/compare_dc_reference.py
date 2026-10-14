"""Existing model against the reference Dixon-Coles model and a blend of the two.

Lang's request of 14 Oct 2026. EPL and La Liga, walk-forward: every match is
predicted at its own lock time (fp.validate.leakage.lock_time) from a fit on results
known by then. The reference model refits at every lock, as the project's fast
Dixon-Coles does; the existing model's forecasts are its stored walk-forward ones.

Stages (the test stage refuses to run until the tune stage has fixed the settings):
    uv run python scripts/compare_dc_reference.py tune   # 2021/22 and 2022/23 only
    uv run python scripts/compare_dc_reference.py test   # 2023/24 to 2025/26, once

Models:
- existing: dc_bayes_v1 with the goals fix shape_v1, the published forecast
  (data/backtests/dc_bayes_v1_walkforward_2021_2025.parquet, fix refitted monthly
  on the previous 730 days).
- dc_mle_v0: the project's own fast Dixon-Coles (ridge and promoted-club priors),
  for context (data/backtests/fast_walkforward_2021_2025.parquet).
- dc_ref: fp.models.dc_reference. No forecast for a team with no match in its
  training window; such matches are counted and handled the same way everywhere.
- blend: weight * existing + (1 - weight) * dc_ref, the existing forecast alone
  where dc_ref has none.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import audit_2026_10 as audit  # noqa: E402
import backtest_trial  # noqa: E402

from fp.evaluate import metrics  # noqa: E402
from fp.ingest.matches import PROCESSED  # noqa: E402
from fp.models import dc_reference as ref  # noqa: E402
from fp.validate.leakage import check_features, known_as_of, lock_time  # noqa: E402

VALIDATION = (2021, 2022)
TEST = (2023, 2024, 2025)
LEAGUES = ("EPL", "LaLiga")
XI_GRID = (0.0, 0.0009, 0.0018, 0.0036)  # 0.0018: the reference's write-up value
WEIGHTS = tuple(round(w, 2) for w in np.arange(0, 1.0001, 0.05))
SETTINGS = ROOT / "data" / "audit" / "dc_reference_settings.json"
PREREG = ROOT / "data" / "audit" / "preregistration_dc_reference_2026_10.md"
PREDS = ROOT / "data" / "backtests" / "dc_reference_walkforward_2021_2025.parquet"
REPORT = ROOT / "reports" / "dc_reference_2026_10.md"
K = ("home", "draw", "away")


# ------------------------------------------------------------------ forecasts
def walk_forward(matches: pd.DataFrame, league: str, seasons: tuple[int, ...],
                 xi: float) -> pd.DataFrame:
    """dc_ref forecasts at each match's lock, from results known at that lock."""
    lg = matches[matches["league"] == league]
    targets = lg[lg["season"].isin(seasons)].copy()
    targets["lock_utc"] = lock_time(targets["kickoff_utc"])
    rows = []
    for lock_key, group in targets.groupby("lock_utc", sort=True):
        lock = cast(pd.Timestamp, lock_key)
        frame = ref.to_reference_frame(lg, lock)
        source_max = known_as_of(lg, lock)["result_available_utc"].max()
        try:
            fit: ref.RefFit | None = ref.fit(frame, xi=xi)
            status_fit = "ok"
        except ref.DCReferenceFitError:
            fit, status_fit = None, "fit_failed"
        for r in group.itertuples():
            p: dict = {}
            status = status_fit
            if fit is not None:
                try:
                    p = fit.predict(str(r.home_id), str(r.away_id))
                except ref.UnseenTeamError:
                    status = "unseen_team"
                except ref.InvalidForecastError:
                    status = "invalid_matrix"
            rows.append({"match_id": r.match_id, "league": league, "season": int(r.season),
                         "lock_utc": lock, "as_of_utc": lock, "source_max_utc": source_max,
                         "status": status, "ref_home": p.get("p_home", np.nan),
                         "ref_draw": p.get("p_draw", np.nan), "ref_away": p.get("p_away", np.nan),
                         "omitted_mass": p.get("omitted_mass", np.nan)})
    out = pd.DataFrame(rows)
    check_features(out)  # fails loudly if any fit saw a result after its lock
    return out


def forecasts(matches: pd.DataFrame, seasons: tuple[int, ...], xi: float) -> pd.DataFrame:
    return pd.concat([walk_forward(matches, lg, seasons, xi) for lg in LEAGUES],
                     ignore_index=True)


def table(matches: pd.DataFrame, refs: pd.DataFrame) -> pd.DataFrame:
    """One row per match: outcome, existing, dc_mle_v0 and dc_ref probabilities."""
    pub = backtest_trial.goals("live", matches)
    fast = pd.read_parquet(ROOT / "data" / "backtests" / "fast_walkforward_2021_2025.parquet")
    t = refs.merge(pub[["match_id", "pub_home", "pub_draw", "pub_away"]], on="match_id",
                   how="left").merge(fast[["match_id", "dc_home", "dc_draw", "dc_away"]],
                                     on="match_id", how="left")
    t = t.rename(columns={f"pub_{k}": f"existing_{k}" for k in K})
    m = matches.set_index("match_id")
    t["outcome"] = metrics.outcome_1x2(t["match_id"].map(m["home_goals"]).to_numpy(int),
                                       t["match_id"].map(m["away_goals"]).to_numpy(int))
    t["kickoff_utc"] = t["match_id"].map(m["kickoff_utc"])
    missing = t[[f"existing_{k}" for k in K] + [f"dc_{k}" for k in K]].isna().any(axis=1)
    if missing.any():
        raise RuntimeError(f"{int(missing.sum())} matches lack an existing forecast")
    return t


# ------------------------------------------------------------------ scores
def probs(t: pd.DataFrame, name: str) -> np.ndarray:
    return t[[f"{name}_{k}" for k in K]].to_numpy(float)


def with_fallback(t: pd.DataFrame) -> np.ndarray:
    """dc_ref where it has a forecast, the existing model where it has none."""
    return ref.blend(probs(t, "existing"), probs(t, "ref"), 0.0)


def calibration(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """(slope, expected calibration error): home, draw, away pooled one-vs-rest.
    Slope 1 is ideal (above 1: too timid); ECE 0 is ideal, over 10 equal-width bins."""
    slope = backtest_trial.slope(p, y)
    pp, yy = p.ravel(), np.eye(3)[y].ravel()
    bins = np.minimum((pp * 10).astype(int), 9)
    ece = sum(abs(pp[bins == b].mean() - yy[bins == b].mean()) * (bins == b).mean()
              for b in range(10) if (bins == b).any())
    return slope, float(ece)


def scores(p: np.ndarray, y: np.ndarray) -> dict:
    slope, ece = calibration(p, y)
    return {"n": len(y), "log_loss": float(metrics.log_loss(p, y).mean()),
            "brier": float(metrics.brier(p, y).mean()), "rps": float(metrics.rps(p, y).mean()),
            "accuracy": float((p.argmax(1) == y).mean()), "calibration_slope": slope,
            "ece": ece}


def paired(a: np.ndarray, b: np.ndarray, y: np.ndarray, seed: int) -> dict:
    """a minus b, per match, with a 95% bootstrap interval (4,000 resamples)."""
    out = {}
    for name, f in (("log_loss", metrics.log_loss), ("brier", metrics.brier)):
        mean, lo, hi, _ = audit.interval(f(a, y) - f(b, y), seed)
        out[name] = {"mean": mean, "lo": lo, "hi": hi}
    return out


# ------------------------------------------------------------------ stages
def tune() -> int:
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    start = time.time()
    by_xi, refs_by_xi = {}, {}
    for xi in XI_GRID:
        t = table(matches, forecasts(matches, VALIDATION, xi))
        ok = t["status"] == "ok"
        refs_by_xi[xi] = t
        by_xi[xi] = {"log_loss_where_available": float(
            metrics.log_loss(probs(t[ok], "ref"), t.loc[ok, "outcome"].to_numpy()).mean()),
            "available": int(ok.sum()), "n": len(t)}
        print(f"xi {xi}: {by_xi[xi]}")
    xi = min(by_xi, key=lambda k: by_xi[k]["log_loss_where_available"])
    t = refs_by_xi[xi]
    y = t["outcome"].to_numpy()
    blend_ll = {w: float(metrics.log_loss(ref.blend(probs(t, "existing"), probs(t, "ref"), w),
                                          y).mean()) for w in WEIGHTS}
    weight = min(blend_ll, key=lambda w: blend_ll[w])
    settings = {"xi": xi, "weight": weight, "fixed_utc": pd.Timestamp.now("UTC").isoformat(),
                "validation_seasons": list(VALIDATION), "xi_grid": by_xi,
                "blend_log_loss_by_weight": blend_ll,
                "prereg_sha256": hashlib.sha256(PREREG.read_bytes()).hexdigest()}
    SETTINGS.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(f"chosen xi {xi}, weight {weight} (existing share); {time.time() - start:.0f}s")
    return 0


def test() -> int:
    if not SETTINGS.exists():
        raise SystemExit("run the tune stage first: settings must be fixed before the test")
    s = json.loads(SETTINGS.read_text(encoding="utf-8"))
    if hashlib.sha256(PREREG.read_bytes()).hexdigest() != s["prereg_sha256"]:
        raise SystemExit("the pre-registration changed after the settings were fixed")
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    xi, w = s["xi"], s["weight"]
    t = table(matches, forecasts(matches, VALIDATION + TEST, xi))
    t.to_parquet(PREDS, index=False)
    t["blend_home"], t["blend_draw"], t["blend_away"] = ref.blend(
        probs(t, "existing"), probs(t, "ref"), w).T
    fb = with_fallback(t)
    t["reffb_home"], t["reffb_draw"], t["reffb_away"] = fb.T
    res: dict = {"settings": s, "periods": {}}
    for label, seasons in (("validation", VALIDATION), ("test", TEST)):
        p = t[t["season"].isin(seasons)]
        y = p["outcome"].to_numpy()
        ok = (p["status"] == "ok").to_numpy()
        per: dict = {"dates": [f"{p['kickoff_utc'].min():%Y-%m-%d}",
                               f"{p['kickoff_utc'].max():%Y-%m-%d}"],
                     "n": len(p), "status": p["status"].value_counts().to_dict(),
                     "max_omitted_mass": float(p["omitted_mass"].max())}
        per["all"] = {name: scores(probs(p, name), y)
                      for name in ("existing", "dc", "reffb", "blend")}
        per["common"] = {name: scores(probs(p[ok], name), y[ok])
                         for name in ("existing", "dc", "ref", "blend")}
        per["blend_minus_existing"] = paired(probs(p, "blend"), probs(p, "existing"), y, 1)
        per["ref_minus_existing_common"] = paired(probs(p[ok], "ref"),
                                                  probs(p[ok], "existing"), y[ok], 2)
        per["by_season"] = {}
        for season in seasons:
            q = p[p["season"] == season]
            yq = q["outcome"].to_numpy()
            d = metrics.log_loss(probs(q, "blend"), yq) - metrics.log_loss(probs(q, "existing"), yq)
            per["by_season"][int(season)] = {"n": len(q), "blend_minus_existing_log_loss":
                                             float(d.mean())}
        res["periods"][label] = per
    d = res["periods"]["test"]["blend_minus_existing"]
    res["retain"] = bool(w < 1 and d["log_loss"]["hi"] < 0 and d["brier"]["mean"] <= 0)
    (ROOT / "data" / "audit" / "dc_reference_2026_10.json").write_text(
        json.dumps(res, indent=2, default=float) + "\n", encoding="utf-8")
    write_report(res)
    print(json.dumps({k: res["periods"][k]["all"] for k in res["periods"]}, indent=1,
                     default=float))
    print("retain the blend:", res["retain"])
    return 0


def write_report(res: dict) -> None:
    s = res["settings"]
    names = {"existing": "Existing (dc_bayes_v1 with shape_v1)", "dc": "dc_mle_v0 (project DC)",
             "ref": "dc_ref (reference DC)", "reffb": "dc_ref, existing where unseen",
             "blend": f"Blend ({s['weight']:.2f} existing)"}

    def rows(block: dict) -> list[str]:
        out = ["| Model | n | Log loss (lower better) | Brier (lower better) | RPS (lower better) "
               "| Accuracy (higher better) | Calibration slope (1 ideal) | ECE (0 ideal) |",
               "|---|---|---|---|---|---|---|---|"]
        for k, v in block.items():
            out.append(f"| {names[k]} | {v['n']} | {v['log_loss']:.4f} | {v['brier']:.4f} | "
                       f"{v['rps']:.4f} | {v['accuracy']:.1%} | {v['calibration_slope']:.3f} | "
                       f"{v['ece']:.4f} |")
        return out

    def diff(d: dict) -> str:
        return ", ".join(f"{m} {d[m]['mean']:+.4f} ({d[m]['lo']:+.4f} to {d[m]['hi']:+.4f})"
                         for m in ("log_loss", "brier"))

    lines = ["# Reference Dixon-Coles against the existing model", "",
             "Generated by `scripts/compare_dc_reference.py`. Rules fixed before the test: "
             "`data/audit/preregistration_dc_reference_2026_10.md`. EPL and La Liga, "
             "walk-forward, each match predicted at its lock from results known then.", "",
             f"Settings chosen on 2021/22 and 2022/23 only: decay xi = {s['xi']} per day, "
             f"blend weight {s['weight']:.2f} on the existing model "
             f"({1 - s['weight']:.2f} on dc_ref).", "",
             "| xi | dc_ref validation log loss (where available) |", "|---|---|"]
    lines += [f"| {k} | {v['log_loss_where_available']:.4f} |" for k, v in s["xi_grid"].items()]
    for label, title in (("validation", "Validation: 2021/22 and 2022/23"),
                         ("test", "Test: 2023/24 to 2025/26 (run once)")):
        p = res["periods"][label]
        lines += ["", f"## {title}", "",
                  f"Dates {p['dates'][0]} to {p['dates'][1]}; {p['n']} matches. dc_ref status: "
                  + ", ".join(f"{k} {v}" for k, v in p["status"].items())
                  + f". Largest probability outside the 10-goal grid: {p['max_omitted_mass']:.2e}.",
                  "", "All matches (dc_ref replaced by the existing forecast where it has none):",
                  "", *rows(p["all"]), "",
                  "Matches where dc_ref has a forecast:", "", *rows(p["common"]), "",
                  f"- Blend minus existing, all matches: {diff(p['blend_minus_existing'])}.",
                  f"- dc_ref minus existing, matches it covers: "
                  f"{diff(p['ref_minus_existing_common'])}.",
                  "- Blend minus existing log loss by season: "
                  + ", ".join(f"{k}/{(int(k) + 1) % 100:02d} "
                              f"{v['blend_minus_existing_log_loss']:+.4f} (n {v['n']})"
                              for k, v in p["by_season"].items()) + "."]
    lines += ["", "## Decision", "",
              ("The blend is retained as an option: on the test seasons its log loss beats "
               "the existing model with the whole 95% interval below zero, and its Brier "
               "score is no worse." if res["retain"] else
               "The blend is not retained. It does not beat the existing model on the test "
               "seasons by the pre-set rule (log loss interval wholly below zero and Brier "
               "no worse). The existing model stays the published one; dc_ref stays a "
               "comparison tool only."), ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    if stage not in ("tune", "test"):
        raise SystemExit("usage: compare_dc_reference.py tune|test")
    sys.exit(tune() if stage == "tune" else test())
