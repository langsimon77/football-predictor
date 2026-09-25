"""Home, draw, away challengers (spec S5.2, Phase 4).

- ordered_logit: ordered logistic regression on the fast Dixon-Coles expected goal
  difference. Home, draw, away treated as ordered outcomes (about a quarter of
  matches are draws, so binary logistic regression would be wrong).
- multinomial: regularised multinomial logistic regression on all features.
- random_forest and xgboost: multiclass tree ensembles on all features.

Settings are chosen by time-ordered cross-validation only: every fold trains on
earlier matches and tests on later ones. Never random K-fold (spec S5.2).
XGBoost is imported only when used: on macOS it needs an OpenMP runtime that
this Mac lacks, so its backtest runs on GitHub's Linux runner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from fp.evaluate import metrics
from fp.features.ml_features import FEATURES
from fp.models import elo

MODELS = ("ordered_logit", "multinomial", "random_forest", "xgboost")
GRIDS: dict[str, list[dict[str, Any]]] = {
    "ordered_logit": [{}],
    "multinomial": [{"C": c} for c in (0.01, 0.1, 1.0)],
    "random_forest": [{"max_depth": d, "min_samples_leaf": leaf}
                      for d in (4, 6, 8) for leaf in (20, 50)],
    "xgboost": [{"max_depth": d, "n_estimators": n} for d in (2, 3) for n in (150, 400)],
}
SEED = 2026


def xgboost_available() -> bool:
    try:
        import xgboost  # noqa: F401
    except Exception:  # missing OpenMP runtime raises XGBoostError, not ImportError
        return False
    return True


@dataclass
class Challenger:
    name: str
    params: dict[str, Any] = field(default_factory=dict)
    fitted: Any = None

    def _estimator(self) -> Any:
        if self.name == "multinomial":
            return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                 LogisticRegression(C=self.params["C"], max_iter=3000))
        if self.name == "random_forest":
            return make_pipeline(SimpleImputer(strategy="median"), RandomForestClassifier(
                n_estimators=500, random_state=SEED, n_jobs=-1, **self.params))
        if self.name == "xgboost":
            from xgboost import XGBClassifier
            return XGBClassifier(objective="multi:softprob", learning_rate=0.03,
                                 subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
                                 random_state=SEED, n_jobs=4, **self.params)
        raise ValueError(self.name)

    def fit(self, train: pd.DataFrame) -> Challenger:
        y = train["outcome"].to_numpy()
        if self.name == "ordered_logit":
            supremacy = (train["dc_exp_goals_home"] - train["dc_exp_goals_away"]).to_numpy()
            # elo.fit_curve codes outcomes 0 away, 1 draw, 2 home; ours are 0 home, 2 away.
            self.fitted = elo.fit_curve(supremacy, 2 - y)
        else:
            self.fitted = self._estimator().fit(train[FEATURES], y)
        return self

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        """Probabilities in the order home, draw, away."""
        if self.name == "ordered_logit":
            supremacy = (rows["dc_exp_goals_home"] - rows["dc_exp_goals_away"]).to_numpy()
            return self.fitted.probs(supremacy)
        p = self.fitted.predict_proba(rows[FEATURES])
        return p[:, np.argsort(self.fitted.classes_)]


def time_series_cv(name: str, rows: pd.DataFrame, folds: int = 4) -> pd.DataFrame:
    """Mean log loss of each setting over expanding-window folds ordered by kickoff."""
    rows = rows.sort_values("kickoff_utc").reset_index(drop=True)
    edges = np.linspace(len(rows) * 0.4, len(rows), folds + 1).astype(int)
    results = []
    for params in GRIDS[name]:
        losses = []
        for start, end in zip(edges[:-1], edges[1:], strict=True):
            train, test = rows.iloc[:start], rows.iloc[start:end]
            p = Challenger(name, params).fit(train).predict(test)
            losses.append(metrics.log_loss(p, test["outcome"].to_numpy()).mean())
        results.append({"model": name, "params": params, "log_loss": float(np.mean(losses))})
    return pd.DataFrame(results)
