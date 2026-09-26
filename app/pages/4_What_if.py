"""What-if simulator (spec S9, page 5). A sandbox: it never touches the ledger."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy.stats import nbinom, poisson

import lib

STARTER_ATTACK, STARTER_CONCEDE, THREAT_ATTACK, CAP = 0.025, 0.025, 0.06, 0.12  # fp.news.impact

lib.setup("What-if simulator")
st.warning("Sandbox: nothing here changes a forecast or the ledger.")
fx = lib.table("fixtures.parquet")
details = lib.table("details.parquet")
if fx.empty or details.empty:
    st.info("No match details in the published data yet.")
    st.stop()
fx = fx[fx["match_id"].isin(details["match_id"])].sort_values("kickoff_utc")
labels = dict(zip(fx["match_id"], lib.juba(fx["kickoff_utc"]).dt.strftime("%a %d %b %H:%M")
                  + "  " + fx["home_name"] + " v " + fx["away_name"], strict=True))
match_id = st.selectbox("Match", list(labels), format_func=labels.get)
row = fx.set_index("match_id").loc[match_id]
d = details.set_index("match_id").loc[match_id]
w = json.loads(d["whatif"])
home_name, away_name = row["home_name"], row["away_name"]

adj = json.loads(row["news_adjustments"]) if isinstance(row["news_adjustments"], str) else []
start = {"home": (0, False), "away": (0, False)}
if adj:
    for side in ("home", "away"):
        a = adj[0].get(side) or {}
        if a.get("status") == "answered":
            start[side] = (int(a["starters_out"]), bool(a["threat_out"]))

st.subheader("Team news")
c1, c2 = st.columns(2)
h_out = c1.slider(f"{home_name}: regular starters out", 0, 3, start["home"][0])
h_threat = c1.checkbox(f"{home_name}: main goal threat out", start["home"][1])
a_out = c2.slider(f"{away_name}: regular starters out", 0, 3, start["away"][0])
a_threat = c2.checkbox(f"{away_name}: main goal threat out", start["away"][1])
st.subheader("Home advantage")
home_k = st.slider("Share of the usual home advantage", 0.0, 2.0, 1.0, 0.25,
                   help="1 is normal. 0 plays the match as if at a neutral ground.")
st.caption("Rest days: the published model does not use them, so there is no control for "
           "them here. The shadow challengers do use rest days.")


def scales(hn: int, ht: bool, an: int, at: bool) -> tuple[float, float]:
    hn, an = max(hn, int(ht)), max(an, int(at))
    home = 1 - hn * STARTER_ATTACK - ht * THREAT_ATTACK + an * STARTER_CONCEDE
    away = 1 - an * STARTER_ATTACK - at * THREAT_ATTACK + hn * STARTER_CONCEDE
    return float(np.clip(home, 1 - CAP, 1 + CAP)), float(np.clip(away, 1 - CAP, 1 + CAP))


def markets(hs: float, as_: float, k: float) -> dict[str, float]:
    lam = np.asarray(w["lam"]) * hs * np.exp(np.asarray(w["home"]) * (k - 1))
    nu = np.asarray(w["nu"]) * as_
    rho = np.asarray(w["rho"])
    g = np.arange(11)
    m = poisson.pmf(g[None, :], lam[:, None])[:, :, None] * \
        poisson.pmf(g[None, :], nu[:, None])[:, None, :]
    m[:, 0, 0] *= 1 - lam * nu * rho
    m[:, 0, 1] *= 1 + lam * rho
    m[:, 1, 0] *= 1 + nu * rho
    m[:, 1, 1] *= 1 - rho
    m = np.clip(m, 0, None)
    m = (m / m.sum(axis=(1, 2), keepdims=True)).mean(axis=0)
    total = np.add.outer(g, g)
    return {"Home win": float(np.tril(m, -1).sum()), "Draw": float(np.trace(m)),
            "Away win": float(np.triu(m, 1).sum()), "Over 2.5 goals": float(m[total > 2.5].sum()),
            "Both teams score": float(m[1:, 1:].sum()),
            "Expected goals, home": float((m.sum(axis=1) * g).sum()),
            "Expected goals, away": float((m.sum(axis=0) * g).sum())}


before = markets(*w["scale"], 1.0)
after = markets(*scales(h_out, h_threat, a_out, a_threat), home_k)

ref = json.loads(d["referee"]) if isinstance(d.get("referee"), str) else None
if ref is not None:
    st.subheader("Referee")
    if ref.get("effects"):
        options = ["Unknown (average over referees)"] + sorted(ref["effects"])
        default = options.index(ref["name"]) if ref.get("known") and ref["name"] in options else 0
        chosen = st.selectbox("Referee", options, index=default)
    else:
        chosen = "Unknown (average over referees)"
        st.caption("The La Liga cards model has no referee effect: referees are named after "
                   "our lock.")
    eta = np.asarray(ref["eta"])
    alpha = np.asarray(ref["alpha"]) if ref.get("alpha") else None
    rng = np.random.default_rng(0)

    def yellows(name: str) -> float:
        if name in (ref.get("effects") or {}):
            e = eta + ref["effects"][name]
        else:
            e = eta + rng.normal(0, ref.get("sigma_ref", 0.0), len(eta))
        mu = np.exp(e)
        k = np.arange(17)
        if alpha is None:
            pmf = poisson.pmf(k[None, :], mu[:, None]).mean(axis=0)
        else:
            a = alpha[:, None]
            pmf = nbinom.pmf(k[None, :], a, a / (a + mu[:, None])).mean(axis=0)
        return float(pmf[k > 4.5].sum())

    start_ref = ref["name"] if ref.get("known") and ref.get("name") else \
        "Unknown (average over referees)"
    before["Over 4.5 yellows"] = yellows(start_ref)
    after["Over 4.5 yellows"] = yellows(chosen)

table = pd.DataFrame({"Market": list(before), "As published": list(before.values()),
                      "What if": [after[k] for k in before]})
table["Change"] = table["What if"] - table["As published"]
fig = go.Figure()
top = table.head(3)
fig.add_bar(x=top["Market"], y=top["As published"], name="As published", marker_color="#999999")
fig.add_bar(x=top["Market"], y=top["What if"], name="What if", marker_color=lib.HOME)
fig.update_layout(barmode="group", height=300, margin=dict(l=0, r=0, t=10, b=0),
                  yaxis=dict(tickformat=".0%", range=[0, 1]), legend=dict(orientation="h"))
lib.chart(fig)
lib.caption("Home, draw, and away chances as published (grey) and with your changes (blue).",
            "The sandbox rescales each side's scoring rate with the same rules as the news "
            "model: each starter out costs 2.5% of the club's scoring and gives its opponent "
            "2.5% more; the main goal threat costs a further 6%; no rate moves more than 12%. "
            "Home advantage multiplies the fitted home effect. All sizes are Assumptions "
            "(Methods, chapter 5).")
fmt = {c: "{:.1%}" for c in ("As published", "What if", "Change")}
shown = table.copy()
for c in fmt:
    shown[c] = [f"{v:.2f}" if "Expected" in m else f"{v:+.1%}" if c == "Change" else f"{v:.1%}"
                for m, v in zip(table["Market"], table[c], strict=True)]
st.dataframe(shown, hide_index=True)
st.caption("Every market before and after your changes.")
