"""Switch-on work for the goals fix `shape_v1` (approved by Lang on 9 Oct 2026).

1. Rebuild the stored walk-forward forecasts with the fix, refitted monthly on the
   previous 730 days only (exactly as the live run will do).
2. Save them as `data/backtests/baselines_2021_2025_shape_v1.parquet`: the weekly
   run's drift norms and stack pool then compare like with like.
3. Refit the confidence cut points for the goals markets by the tiers_v1 rule
   (top quarter High, bottom third Low, widest or most disputed tenth drops one
   level) on the tuning seasons 2021/22 and 2022/23. The width cut is scaled by how
   much the fix widens the 80% intervals, measured on every pairing of this
   season's clubs under the current posterior. Corners and yellows are unchanged.
4. Write the first month's numbers to `data/shape/shape_v1.json`.
5. Report: `reports/shape_v1_rollout.md`.

    uv run python scripts/shape_v1_rollout.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import audit_2026_10 as audit  # noqa: E402
import stack_steadiness  # noqa: E402

from fp.ensemble import stacking, tiers  # noqa: E402
from fp.ingest.matches import PROCESSED  # noqa: E402
from fp.models import bayes_dc, shape  # noqa: E402
from fp.models.priors import PromotedPrior  # noqa: E402
from fp.models.promotion import fit_promotion_model  # noqa: E402
from fp.pipeline import daily  # noqa: E402

BT = ROOT / "data" / "backtests"
OUT_BASE = BT / "baselines_2021_2025_shape_v1.parquet"
TIERS_FILE = ROOT / "data" / "tiers" / "thresholds.json"
REPORT = ROOT / "reports" / "shape_v1_rollout.md"
TUNE = (2021, 2022)
TEST = (2023, 2024, 2025)
GOAL_MARKETS = ("over_1_5", "over_2_5", "over_3_5", "btts")
NOW = pd.Timestamp("2026-10-09T12:00Z")


def rolling_tables(f: pd.DataFrame) -> tuple[np.ndarray, list]:
    lam, nu = f["lam"].to_numpy(), f["nu"].to_numpy()
    hg, ag = f["hg"].to_numpy(), f["ag"].to_numpy()
    rows, path = audit.monthly(
        f, lambda idx, prev: shape.fit(lam[idx], nu[idx], hg[idx], ag[idx], prev),
        lambda sel, sh: list(shape.shaped(lam[sel], nu[sel], sh)), shape.POISSON)
    return np.stack(rows), path


def width_ratio() -> dict[str, float]:
    """How much wider the fix makes the 80% intervals: the 90th percentile of
    widths with the fix over the 90th percentile without, on every pairing of this
    season's clubs under today's posterior."""
    matches = pd.read_parquet(PROCESSED / "matches.parquet")
    fixtures = pd.read_parquet(PROCESSED / "fixtures.parquet")
    second = pd.read_parquet(PROCESSED / "second_tier.parquet")
    prior, promo = PromotedPrior(matches), fit_promotion_model(matches, second)
    season = int(fixtures["season"].max())
    sh = shape.current(matches, pd.DataFrame(), NOW, save=False)
    plain_w: dict[str, list[float]] = {}
    fixed_w: dict[str, list[float]] = {}
    with tempfile.TemporaryDirectory() as store:
        for league in daily.LEAGUES:
            lm = daily.fit_league(matches, fixtures, league, NOW, prior, season, second, promo,
                                  with_bayes=True, store=Path(store))
            post = lm.bayes
            assert post is not None
            clubs = sorted(set(fixtures.loc[fixtures["league"] == league, "home_id"]))
            for h in clubs:
                for a in clubs:
                    if h == a:
                        continue
                    plain = bayes_dc.markets(post, h, a)
                    lam, nu = post.rates(h, a)
                    fixed = shape.apply(plain, lam, nu, sh)
                    top = ["p_home", "p_draw", "p_away"][int(np.argmax(
                        [fixed["p_home"], fixed["p_draw"], fixed["p_away"]]))]
                    for key, name in [("1x2", top)] + [(m, f"p_{m}") for m in GOAL_MARKETS]:
                        for store_w, mk in ((plain_w, plain), (fixed_w, fixed)):
                            lo, hi = mk["intervals"][name]
                            store_w.setdefault(key, []).append(hi - lo)
    return {k: float(np.quantile(fixed_w[k], 0.9) / np.quantile(plain_w[k], 0.9))
            for k in plain_w}


def main() -> int:
    f = audit.goals_frame()
    M, path = rolling_tables(f)
    mk = audit.markets(M)
    shaped = pd.DataFrame({"match_id": f["match_id"], "p_home": mk["x12"][:, 0],
                           "p_draw": mk["x12"][:, 1], "p_away": mk["x12"][:, 2],
                           "p_over_1_5": mk["over_1_5"], "p_over_2_5": mk["over_2_5"],
                           "p_over_3_5": mk["over_3_5"], "p_btts": mk["btts"]}).set_index(
        "match_id")

    # 2. Baselines for the weekly run, with the fix.
    base = pd.read_parquet(BT / "baselines_2021_2025.parquet")
    new = base.copy()
    for c in ("p_home", "p_draw", "p_away", "p_over_2_5"):
        new[c] = new["match_id"].map(shaped[c])
    assert new[["p_home", "p_draw", "p_away", "p_over_2_5"]].notna().all().all()
    new.to_parquet(OUT_BASE, index=False)

    # 3. Cut points by the same rule, tuning seasons only.
    ratio = width_ratio()
    old = tiers.load(TIERS_FILE)
    data = json.loads(TIERS_FILE.read_text(encoding="utf-8"))
    b = new.set_index("match_id").reindex(f["match_id"])
    tune = f["season"].isin(TUNE).to_numpy()
    test = f["season"].isin(TEST).to_numpy()
    iv = f["bdc_intervals"].map(json.loads).tolist()
    p = mk["x12"]
    top = p.argmax(1)
    names = np.array(["p_home", "p_draw", "p_away"])
    width = np.array([d[n][1] - d[n][0] for d, n in zip(iv, names[top], strict=True)])
    y = f["y"].to_numpy()
    # Disagreement: the stack against the main model, the stack cross-fitted on the
    # tuning seasons (weights from the other season), as in Phase 4.
    comp = {m: stack_steadiness.component(b, m) for m in stack_steadiness.MODELS}
    seasons = f["season"].to_numpy()
    stack_cf = np.full_like(p, np.nan)
    for s_fit, s_use in ((2022, 2021), (2021, 2022)):
        w = stacking.fit({m: c[seasons == s_fit] for m, c in comp.items()},
                         y[seasons == s_fit]).weights
        stack_cf[seasons == s_use] = sum(wj * comp[m][seasons == s_use]
                                         for m, wj in zip(stack_steadiness.MODELS, w,
                                                          strict=True))
    live_w = np.asarray(json.loads((ROOT / "data" / "stacking" / "stack_1x2.json")
                                   .read_text())["weights"])
    stack_live = sum(wj * comp[m] for m, wj in zip(stack_steadiness.MODELS, live_w,
                                                   strict=True))
    dis = 0.5 * np.abs(np.where(tune[:, None], stack_cf, stack_live) - p).sum(1)
    th1 = tiers.fit("1x2", p.max(1)[tune], width[tune], dis[tune],
                    basis="dc_bayes_v1 with shape_v1, 2021/22 and 2022/23 (refit 9 Oct 2026)")
    th1.width_max = round(float(th1.width_max or 0) * ratio["1x2"], 3)
    refit = {"1x2": th1}
    for m in GOAL_MARKETS:
        pm = mk[m]
        fav = np.maximum(pm, 1 - pm)
        wd = np.array([d[f"p_{m}"][1] - d[f"p_{m}"][0] for d in iv])
        th = tiers.fit(m, fav[tune], wd[tune],
                       basis="dc_bayes_v1 with shape_v1, 2021/22 and 2022/23 (refit 9 Oct 2026)")
        th.width_max = round(float(th.width_max or 0) * ratio[m], 3)
        refit[m] = th
    for t in data["thresholds"]:
        if t["market"] in refit:
            t.update({k: v for k, v in vars(refit[t["market"]]).items()})
    data["width_scale"] = {k: round(v, 3) for k, v in ratio.items()}
    data["refit"] = ("Goals cut points refit by the same rule for shape_v1 (Lang approved "
                     "9 Oct 2026); width cuts scaled by the measured widening "
                     + ", ".join(f"{k} x{v:.3f}" for k, v in ratio.items()) + ".")
    TIERS_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    # Separation on the test seasons: old cut points with plain forecasts against
    # new cut points with the fix (widths: stored plain intervals, scaled cut undone).
    p0 = f[["bdc_home", "bdc_draw", "bdc_away"]].to_numpy(dtype=float)
    w0 = np.array([d[n][1] - d[n][0] for d, n in zip(iv, names[p0.argmax(1)], strict=True)])
    dis0 = 0.5 * np.abs(stack_live - p0).sum(1)
    th1_eval = tiers.Thresholds(**{**vars(th1), "width_max": th1.width_max / ratio["1x2"]})
    rows = []
    for label, th, pp, ww, dd in (("before: plain forecast, old cut points", old["1x2"], p0, w0,
                                   dis0),
                                  ("after: fixed forecast, new cut points", th1_eval, p, width,
                                   0.5 * np.abs(stack_live - p).sum(1))):
        lvl = tiers.assign(th, pp.max(1)[test], np.zeros(int(test.sum()), dtype=int),
                           width=ww[test], disagree=dd[test])
        hit = (pp.argmax(1) == y)[test]
        fav = pp.max(1)[test]
        for t in ("High", "Medium", "Low"):
            sel = lvl == t
            rows.append((label, t, int(sel.sum()), float(fav[sel].mean()), float(hit[sel].mean())))

    # 4. This month's numbers for the live run.
    sh = shape.current(pd.read_parquet(PROCESSED / "matches.parquet"), pd.DataFrame(), NOW,
                       save=True)
    write_report(path, ratio, old, refit, rows, sh)
    print(f"wrote {OUT_BASE}, {TIERS_FILE}, {shape.STORE}, {REPORT}")
    return 0


def write_report(path, ratio, old, refit, rows, sh) -> None:
    lines = ["# shape_v1 switch-on", "",
             "Generated by `scripts/shape_v1_rollout.py`. Lang approved the goals fix on "
             "9 Oct 2026 (`docs/MODEL_CHANGELOG.md`). Nothing here edits a locked forecast.", "",
             "## Numbers for October 2026", "",
             f"Home dispersion {sh.vh:.4f}, away dispersion {sh.va:.4f}, rho {sh.rho:+.4f}, "
             f"stretch {sh.s:+.4f} (`data/shape/shape_v1.json`).", "",
             "## Monthly refits replayed over the backtest", "",
             "| Month | Matches of history | Home dispersion | Away dispersion | Rho | Stretch |",
             "|---|---|---|---|---|---|"]
    for mth, n, s in path[::3]:
        lines.append(f"| {mth} | {n} | {s.vh:.3f} | {s.va:.3f} | {s.rho:+.4f} | {s.s:+.4f} |")
    lines += ["", "## Confidence cut points, refit by the tiers_v1 rule on 2021/22 and 2022/23",
              "", "| Market | High from (old, new) | Low below (old, new) | Width cut (old, new) "
              "| Disagreement cut (old, new) |", "|---|---|---|---|---|"]
    for m, th in refit.items():
        o = old[m]
        lines.append(f"| {m} | {o.high:.2f}, {th.high:.2f} | {o.low:.2f}, {th.low:.2f} | "
                     f"{o.width_max}, {th.width_max} | {o.disagree_max}, {th.disagree_max} |")
    lines += ["", "Width cuts are scaled by how much the fix widens the 80% intervals (90th "
              "percentile with the fix over without, every pairing of this season's clubs "
              "under the 9 Oct posterior): " + ", ".join(f"{k} x{v:.3f}" for k, v in
                                                          ratio.items()) + ". [E]", "",
              "## Home, draw, away confidence on the test seasons 2023/24 to 2025/26", "",
              "| Version | Level | Matches | Promised | Won |", "|---|---|---|---|---|"]
    for label, t, n, fav, hit in rows:
        lines.append(f"| {label} | {t} | {n} | {fav:.1%} | {hit:.1%} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    np.seterr(all="ignore")
    sys.exit(main())
