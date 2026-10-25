"""Basketball phase B2: the seven challengers and the way they are fitted.

Plan: data/audit/preregistration_basketball_b2_2026_10.md, sections 2 and 3.

C1 to C5 are machine-learning models refitted at the start of each season and every 28 days on
all earlier games; their winner forecast is the model's own chance, their margin and total a
bell curve around the model's value. C6 (Kalman-filter ratings) and C7 (points model with a home
edge per club) update every game day and give expected scores; their winner forecast is the
chance the margin bell curve lands above zero.

Not tuned, fixed here before any fit: random forests use 300 trees; every model uses the random
seed 2027; the neural network stops early on a held-back tenth of its training games; the
Kalman filter's game-to-game noise uses the B1 points model's measured widths.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from features import BASE, SEQ
from models import _day_groups, _row

SEED = 2027
REFIT_DAYS = 28
MARKETS = ("winner", "margin", "total")

GRIDS: dict[str, list[dict]] = {
    "C1": [{"penalty": p} for p in (0.01, 0.1, 1, 10)],
    "C2": [{"depth": d, "leaf": n} for d in (3, 5, 8) for n in (20, 50)],
    "C3": [{"depth": d, "lr": lr, "rounds": r} for d in (2, 3) for lr in (0.03, 0.1)
           for r in (100, 300)],
    "C4": [{"leaves": lv, "lr": lr, "rounds": r, "l2": l2} for lv in (7, 15) for lr in (0.03, 0.1)
           for r in (100, 300) for l2 in (0, 1)],
    "C5": [{"hidden": h, "penalty": a} for h in (16, 32) for a in (0.001, 0.01)],
    "C6": [{"drift": q, "season_drift": s} for q in (0.02, 0.05, 0.1, 0.2) for s in (5, 20, 50)],
    "C7": [{"home_penalty": p} for p in (1, 3, 10, 30)],
}
NAMES = {"C1": "GLM (logistic and linear regression)", "C2": "Random forest",
         "C3": "XGBoost", "C4": "Histogram gradient boosting (LightGBM method)",
         "C5": "Small neural network on the last 10 results",
         "C6": "Kalman-filter ratings", "C7": "Points model with a home edge per club"}
ML = ("C1", "C2", "C3", "C4", "C5")


def feature_columns(cid: str) -> list[str]:
    return ["elo_diff", *SEQ] if cid == "C5" else BASE


def make_model(cid: str, market: str, p: dict):
    """A fresh scikit-learn style model: a classifier for the winner, a regressor otherwise."""
    from sklearn.compose import TransformedTargetRegressor
    from sklearn.ensemble import (
        HistGradientBoostingClassifier,
        HistGradientBoostingRegressor,
        RandomForestClassifier,
        RandomForestRegressor,
    )
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.neural_network import MLPClassifier, MLPRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    win = market == "winner"
    if cid == "C1":
        return make_pipeline(StandardScaler(), LogisticRegression(C=1 / p["penalty"], max_iter=2000)
                             if win else Ridge(alpha=p["penalty"]))
    if cid == "C2":
        cls = RandomForestClassifier if win else RandomForestRegressor
        return cls(n_estimators=300, max_depth=p["depth"], min_samples_leaf=p["leaf"],
                   random_state=SEED, n_jobs=-1)
    if cid == "C3":
        import xgboost as xgb  # on macOS needs scikit-learn's OpenMP library (CHECKPOINT notes)
        cls = xgb.XGBClassifier if win else xgb.XGBRegressor
        return cls(max_depth=p["depth"], learning_rate=p["lr"], n_estimators=p["rounds"],
                   random_state=SEED, n_jobs=4, verbosity=0)
    if cid == "C4":
        cls = HistGradientBoostingClassifier if win else HistGradientBoostingRegressor
        return cls(max_leaf_nodes=p["leaves"], learning_rate=p["lr"], max_iter=p["rounds"],
                   l2_regularization=p["l2"], random_state=SEED)
    if cid == "C5":
        kw = {"hidden_layer_sizes": (p["hidden"],), "alpha": p["penalty"], "early_stopping": True,
              "max_iter": 500, "random_state": SEED}
        if win:
            return make_pipeline(StandardScaler(), MLPClassifier(**kw))
        return TransformedTargetRegressor(make_pipeline(StandardScaler(), MLPRegressor(**kw)),
                                          transformer=StandardScaler())
    raise ValueError(cid)


def targets(games: pd.DataFrame) -> dict[str, np.ndarray]:
    hp, ap = games["home_pts"].to_numpy(float), games["away_pts"].to_numpy(float)
    return {"winner": (hp > ap).astype(float), "margin": hp - ap, "total": hp + ap}


def refit_blocks(games: pd.DataFrame, rows: np.ndarray) -> list[tuple[int, np.ndarray]]:
    """(refit day, row positions) blocks for the rows to forecast: each season starts a block,
    and a new block begins every 28 days after the season's first game day."""
    ordinal = np.array([d.toordinal() for d in games["date"]])
    seasons = games["season"].to_numpy()
    out = []
    for s in sorted(set(seasons[rows])):
        in_season = np.flatnonzero(seasons == s)
        first = ordinal[in_season].min()
        block = (ordinal[in_season] - first) // REFIT_DAYS
        for b in sorted(set(block)):
            members = in_season[block == b]
            members = members[np.isin(members, rows)]
            if len(members):
                out.append((int(first + b * REFIT_DAYS), members))
    return out


def ml_predict(cid: str, market: str, p: dict, games: pd.DataFrame, X: pd.DataFrame,
               rows: np.ndarray) -> np.ndarray:
    """Forecasts for `rows`, each from a model fitted on games before its block's refit day."""
    y = targets(games)[market]
    cols = feature_columns(cid)
    data = X[cols].to_numpy(float)
    ordinal = np.array([d.toordinal() for d in games["date"]])
    usable = ~np.isnan(data).any(axis=1)
    out = np.full(len(games), np.nan)
    for day, members in refit_blocks(games, rows):
        train = usable & (ordinal < day)
        model = make_model(cid, market, p)
        model.fit(data[train], y[train])
        if market == "winner":
            out[members] = model.predict_proba(data[members])[:, 1]
        else:
            out[members] = model.predict(data[members])
    return out


def kalman_run(games: pd.DataFrame, drift: float, season_drift: float, sd_home: float,
               sd_away: float, rho: float) -> pd.DataFrame:
    """C6. State: league average, home edge, each club's attack and defence. Each day every
    club rating gains `drift` x days of variance (they may wander), plus `season_drift` at a new
    season; then the day's scores update the state (Kalman filter). Forecasts use the state
    before the day's update."""
    clubs = sorted(set(games["home_id"]) | set(games["away_id"]))
    col = {c: i for i, c in enumerate(clubs)}
    n = 2 + 2 * len(clubs)
    att = lambda c: 2 + col[c]  # noqa: E731
    dfn = lambda c: 2 + len(clubs) + col[c]  # noqa: E731
    x = np.zeros(n)
    x[0] = float(games["home_pts"].iloc[:20].mean() + games["away_pts"].iloc[:20].mean()) / 2
    big = np.full(n, 16.0)
    big[0], big[1] = 400.0, 25.0
    p = np.diag(big)
    club_idx = np.arange(2, n)
    r_one = np.array([[sd_home**2, rho * sd_home * sd_away], [rho * sd_home * sd_away, sd_away**2]])
    ordinal = np.array([d.toordinal() for d in games["date"]])
    seasons = games["season"].to_numpy()
    home, away = games["home_id"].to_numpy(), games["away_id"].to_numpy()
    hp, ap = games["home_pts"].to_numpy(float), games["away_pts"].to_numpy(float)
    m_home, m_away = np.full(len(games), np.nan), np.full(len(games), np.nan)
    last_day, season = None, None
    for idx in _day_groups(games):
        day = ordinal[idx[0]]
        if last_day is not None:
            p[club_idx, club_idx] += drift * (day - last_day)
            p[0, 0] += 1e-4 * (day - last_day)
            p[1, 1] += 1e-4 * (day - last_day)
        if season is not None and seasons[idx[0]] != season:
            p[club_idx, club_idx] += season_drift
        season = seasons[idx[0]]
        h = np.vstack([np.vstack([_row(n, (0, 1, att(home[i])), (dfn(away[i]),)),
                                  _row(n, (0, att(away[i])), (dfn(home[i]),))]) for i in idx])
        pred = h @ x
        m_home[idx], m_away[idx] = pred[0::2], pred[1::2]
        y = np.column_stack([hp[idx], ap[idx]]).ravel()
        r = np.kron(np.eye(len(idx)), r_one)
        s = h @ p @ h.T + r
        k = np.linalg.solve(s, h @ p).T
        x = x + k @ (y - pred)
        p = p - k @ h @ p
        p = (p + p.T) / 2
        last_day = day
    return pd.DataFrame({"m_home": m_home, "m_away": m_away}, index=games.index)


def points_home_run(games: pd.DataFrame, half_life: float, penalty: float,
                    home_penalty: float) -> pd.DataFrame:
    """C7: the B1 points model plus an extra home edge for each club, pulled toward zero (the
    league's edge) by `home_penalty`. Walks forward like models.points_run."""
    clubs = sorted(set(games["home_id"]) | set(games["away_id"]))
    col = {c: i for i, c in enumerate(clubs)}
    k = len(clubs)
    n = 2 + 3 * k
    att = lambda c: 2 + col[c]  # noqa: E731
    dfn = lambda c: 2 + k + col[c]  # noqa: E731
    hom = lambda c: 2 + 2 * k + col[c]  # noqa: E731
    pen = np.concatenate([[1e-9, 1e-9], np.full(2 * k, penalty), np.full(k, home_penalty)])
    xtx, xty = np.zeros((n, n)), np.zeros(n)
    ordinal = np.array([d.toordinal() for d in games["date"]], dtype=float)
    home, away = games["home_id"].to_numpy(), games["away_id"].to_numpy()
    hp, ap = games["home_pts"].to_numpy(float), games["away_pts"].to_numpy(float)
    m_home, m_away = np.full(len(games), np.nan), np.full(len(games), np.nan)
    last_day, seen, pending = None, 0, []
    for idx in _day_groups(games):
        day = ordinal[idx[0]]
        if last_day is not None:
            factor = 0.5 ** ((day - last_day) / half_life)
            xtx *= factor
            xty *= factor
        for i in pending:
            w = 0.5 ** ((day - ordinal[i]) / half_life)
            for row, y in ((_row(n, (0, 1, att(home[i]), hom(home[i])), (dfn(away[i]),)), hp[i]),
                           (_row(n, (0, att(away[i])), (dfn(home[i]),)), ap[i])):
                xtx += w * np.outer(row, row)
                xty += w * row * y
            seen += 1
        if seen:
            beta = np.linalg.solve(xtx + np.diag(pen), xty)
            for i in idx:
                m_home[i] = (beta[0] + beta[1] + beta[att(home[i])] + beta[hom(home[i])]
                             - beta[dfn(away[i])])
                m_away[i] = beta[0] + beta[att(away[i])] - beta[dfn(home[i])]
        pending = list(idx)
        last_day = day
    return pd.DataFrame({"m_home": m_home, "m_away": m_away}, index=games.index)


def score_predict(cid: str, p: dict, games: pd.DataFrame, b1: dict) -> pd.DataFrame:
    """Expected scores from C6 or C7 for every game (walk-forward, every game day)."""
    pt = b1["points"]
    if cid == "C6":
        return kalman_run(games, p["drift"], p["season_drift"], pt["sd_home"], pt["sd_away"],
                          pt["rho"])
    if cid == "C7":
        return points_home_run(games, pt["half_life"], pt["penalty"], p["home_penalty"])
    raise ValueError(cid)
