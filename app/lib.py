"""Shared helpers for the dashboard pages.

The dashboard only reads files the daily run precomputed (spec S9). It looks in
FP_DATA_DIR, then app/data/ in this checkout, then the published copy at
FP_DATA_URL (the GitHub Pages site). It never imports the modelling package, so
Streamlit Cloud installs only app/requirements.txt.
"""

from __future__ import annotations

import io
import json
import os
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

APP = Path(__file__).resolve().parent
REPO = APP.parent
LOCAL = Path(os.environ.get("FP_DATA_DIR", APP / "data"))
DATA_URL = os.environ.get("FP_DATA_URL",
                          "https://langsimon77.github.io/football-predictor/data")
JUBA = "Africa/Juba"
ISSUES = "https://github.com/langsimon77/football-predictor/issues"

# Okabe-Ito: safe for the common kinds of colour blindness.
HOME, DRAW, AWAY = "#0072B2", "#999999", "#D55E00"
TIER_COLOURS = {"High": "#009E73", "Medium": "#E69F00", "Low": "#CC79A7"}
SEQUENTIAL = "Blues"
MODEL_NAMES = {
    "dc_bayes_v1": "Bayesian (published)", "dc_bayes_v1_nonews": "Bayesian without news",
    "dc_mle_v0": "Fast Dixon-Coles", "elo_v0": "Elo", "stack_v1": "Stack (shadow)",
    "ordered_logit_v1": "Ordered logit (shadow)", "multinomial_v1": "Multinomial (shadow)",
    "random_forest_v1": "Random Forest (shadow)", "xgboost_v1": "XGBoost (shadow)",
    "base_rates": "League base rates", "market_friday": "Market, Friday snapshot",
    "market_close": "Market, closing",
}


def _bytes(name: str) -> bytes | None:
    for folder in (LOCAL, APP / "data"):
        path = folder / name
        if path.exists():
            return path.read_bytes()
    try:
        with urllib.request.urlopen(f"{DATA_URL}/{name}", timeout=20) as response:
            return response.read()
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def table(name: str) -> pd.DataFrame:
    raw = _bytes(name)
    if raw is None:
        return pd.DataFrame()
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(raw))
    return pd.read_parquet(io.BytesIO(raw))


@st.cache_data(ttl=3600, show_spinner=False)
def document(name: str) -> object:
    raw = _bytes(name)
    return json.loads(raw) if raw else None


def doc_text(relative: str) -> str:
    path = REPO / relative
    return path.read_text(encoding="utf-8") if path.exists() else ""


def caption(text: str, explain: str) -> None:
    """Every chart gets a one-line caption and an "Explain this" expander (spec S9)."""
    st.caption(text)
    with st.expander("Explain this"):
        st.markdown(explain)


def juba(ts: pd.Series | pd.Timestamp, utc: bool = False) -> pd.Series | pd.Timestamp:
    zone = "UTC" if utc else JUBA
    if isinstance(ts, pd.Series):
        return pd.to_datetime(ts, utc=True).dt.tz_convert(zone)
    return pd.Timestamp(ts).tz_convert(zone)


def league_name(code: str) -> str:
    return "La Liga" if code == "LaLiga" else str(code)


def tier_of(tiers: object, market: str = "1x2") -> str:
    if isinstance(tiers, str) and tiers:
        return str(json.loads(tiers).get(market, ""))
    return ""


def updated_line() -> None:
    meta = document("meta.json")
    if isinstance(meta, dict):
        when = juba(pd.Timestamp(meta["generated_utc"]))
        st.caption(f"Data from the daily run of {when:%a %d %b %Y, %H:%M} Juba time.")
    else:
        st.warning("No data yet: the daily run has not published dashboard files.")


def chart(fig: object) -> None:
    """A Plotly chart without the toolbar, which covers small screens."""
    fig.update_layout(font=dict(size=12))  # type: ignore[attr-defined]
    st.plotly_chart(fig, config={"displayModeBar": False, "scrollZoom": False})


def setup(title: str) -> None:
    st.set_page_config(page_title=title, page_icon=":soccer:", layout="centered")
    st.title(title)


# Scoring rules (the same as fp.evaluate.metrics; repeated so the app stays light).
def rps(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    obs = np.eye(3)[y]
    d = np.cumsum(p, axis=1)[:, :2] - np.cumsum(obs, axis=1)[:, :2]
    return (d ** 2).sum(axis=1) / 2


def log_loss(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    return -np.log(np.clip(p[np.arange(len(y)), y], 1e-15, 1))


def brier(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    return ((p - np.eye(3)[y]) ** 2).sum(axis=1)


def calibration_points(p: np.ndarray, y: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """Forecasts for all three outcomes, grouped into equal-size bins."""
    f, o = p.ravel(), np.eye(3)[y].ravel()
    order = np.argsort(f)
    groups = np.array_split(order, min(bins, max(len(f) // 20, 1)))
    return pd.DataFrame({"forecast": [f[g].mean() for g in groups],
                         "observed": [o[g].mean() for g in groups],
                         "n": [len(g) for g in groups]})
