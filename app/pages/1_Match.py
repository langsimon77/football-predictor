"""Match deep-dive (spec S9, page 2)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import lib

lib.setup("Match deep-dive")
lib.updated_line()
fx = lib.table("fixtures.parquet")
details = lib.table("details.parquet")
if fx.empty or details.empty:
    st.info("No match details in the published data yet.")
    st.stop()

fx = fx[fx["match_id"].isin(details["match_id"])].sort_values("kickoff_utc")
fx["label"] = (lib.juba(fx["kickoff_utc"]).dt.strftime("%a %d %b %H:%M") + "  "
               + fx["home_name"] + " v " + fx["away_name"])
ids = fx["match_id"].tolist()
start = st.query_params.get("match")
match_id = st.selectbox("Match", ids, index=ids.index(start) if start in ids else 0,
                        format_func=dict(zip(fx["match_id"], fx["label"], strict=True)).get)
st.query_params["match"] = match_id
row = fx.set_index("match_id").loc[match_id]
d = details.set_index("match_id").loc[match_id]
home, away = row["home_name"], row["away_name"]
tiers = json.loads(row["tiers"]) if isinstance(row["tiers"], str) else {}

status = "Locked" if row["locked"] else "Provisional: updates daily until it locks"
st.subheader(f"{home} v {away}")
st.write(f"{lib.league_name(row['league'])}, {row['round']}. Kickoff "
         f"{lib.juba(row['kickoff_utc']):%a %d %b, %H:%M} Juba time. {status}. "
         f"Tier (home, draw, away): **{tiers.get('1x2', 'none')}**.")
m1, m2, m3 = st.columns(3)
m1.metric(f"{home} win", f"{row['p_home']:.0%}")
m2.metric("Draw", f"{row['p_draw']:.0%}")
m3.metric(f"{away} win", f"{row['p_away']:.0%}")

# Scoreline heatmap.
matrix = np.asarray(d["matrix"], dtype=float).reshape(11, 11)[:7, :7]
fig = px.imshow(matrix * 100, color_continuous_scale=lib.SEQUENTIAL, origin="upper",
                labels=dict(x=f"{away} goals", y=f"{home} goals", color="Chance (%)"),
                text_auto=".1f", aspect="auto")
fig.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0), coloraxis_showscale=False)
lib.chart(fig)
lib.caption("Chance of each scoreline, in percent; the darker, the likelier.",
            "Each cell is the chance of that exact score, from the Bayesian Dixon-Coles "
            "model. The model gives each side a scoring rate from its attack, the "
            "opponent's defence, and home advantage, then adjusts the chances of 0-0, 1-0, "
            "0-1, and 1-1, which plain independent counts get slightly wrong. Scores above 6 "
            "goals are not shown but are counted in every market.")


def distribution(pmf: list[float], lines: tuple[float, ...], title: str, unit: str) -> None:
    k = np.arange(len(pmf))
    fig = go.Figure(go.Bar(x=k, y=pmf, marker_color=lib.HOME,
                           hovertemplate="%{x} " + unit + ": %{y:.1%}<extra></extra>"))
    overs = []
    for line in lines:
        over = float(np.sum(np.asarray(pmf)[k > line]))
        fig.add_vline(x=line, line_dash="dot", line_color=lib.AWAY)
        overs.append(f"over {line}: **{over:.0%}**")
    st.markdown(f"**{title}**: " + ", ".join(overs))
    fig.update_layout(height=240, margin=dict(l=0, r=0, t=10, b=0),
                      yaxis=dict(tickformat=".0%"), xaxis=dict(dtick=2))
    lib.chart(fig)


total = np.zeros(21)
full = np.asarray(d["matrix"], dtype=float).reshape(11, 11)
for i in range(11):
    for j in range(11):
        total[i + j] += full[i, j]
distribution(total[:11].tolist(), (1.5, 2.5, 3.5), "Total goals", "goals")
lib.caption("Chance of each number of goals in the match; dotted lines mark the betting "
            "lines.", "Summed from the scoreline table above. The label on each line is the "
            "chance of going over it.")


def values(x: object) -> list[float] | None:
    return list(x) if isinstance(x, (list, np.ndarray)) else None


if (corners := values(d.get("corners_pmf"))) is not None:
    distribution(corners[:21], (8.5, 9.5, 10.5, 11.5), "Total corners",
                 "corners")
    lib.caption("Chance of each number of corners in the match.",
                "From a Poisson model of the match total: each club's corner tendency, how "
                "lopsided the match looks (Elo gap at lock), and both sides' recent shots. "
                "Home and away corners pull against each other, so the model works on the "
                "total. See Methods, chapter 3b.")
if (cards := values(d.get("cards_pmf"))) is not None:
    distribution(cards[:13], (3.5, 4.5, 5.5), "Total yellow cards", "yellows")
    lib.caption("Chance of each number of yellow cards in the match.",
                "From a negative binomial model: each club's discipline, closeness, recent "
                "fouls, derby, late-season importance, and in the EPL the referee when known "
                "at lock. See Methods, chapter 3b.")

# Model by model.
models = pd.DataFrame(json.loads(d["models"]))
if len(models):
    models["name"] = models["model"].map(lib.MODEL_NAMES).fillna(models["model"])
    fig = go.Figure()
    for col, name, colour in (("p_home", home, lib.HOME), ("p_draw", "Draw", lib.DRAW),
                              ("p_away", away, lib.AWAY)):
        fig.add_bar(y=models["name"], x=models[col], name=name, orientation="h",
                    marker_color=colour,
                    text=[f"{v:.0%}" if v >= 0.15 else "" for v in models[col]],
                    textposition="inside", textangle=0, insidetextanchor="middle")
    fig.update_layout(barmode="stack", height=80 + 32 * len(models),
                      margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(tickformat=".0%"),
                      legend=dict(orientation="h", y=1.0, yanchor="bottom",
                                  traceorder="normal"),
                      yaxis=dict(automargin=True, tickfont=dict(size=11)))
    lib.chart(fig)
    lib.caption("What each model says; only the Bayesian model is published.",
                "Shadow models are locked every day so their records build up, but never "
                "published. The stack blends all seven with weights learned on 2021/22 and "
                "2022/23. It was not clearly better than the Bayesian model on the test "
                "seasons, so it waits for a re-test at the end of 2026/27. See Methods, "
                "chapter 4.")

st.subheader("Top drivers")
for line in json.loads(d["drivers"]):
    st.markdown(f"- {line}")
st.caption("The five facts that most set this forecast apart from an ordinary match.")

st.subheader("Team news")
adj = json.loads(row["news_adjustments"]) if isinstance(row["news_adjustments"], str) else []
unanswered = (json.loads(row["unanswered_questions"])
              if isinstance(row["unanswered_questions"], str) else [])
if adj:
    rec = adj[0]
    st.write(f"{home} scoring rate x{rec['scale_home_goals']:.3f}, {away} scoring rate "
             f"x{rec['scale_away_goals']:.3f}" + (" (capped at 12%)." if rec["capped"] else "."))
elif unanswered:
    st.write("Question asked but not answered: no news applied, tier capped at Medium.")
else:
    st.write("No news applied.")

if isinstance(d.get("referee"), str):
    ref = json.loads(d["referee"])
    st.subheader("Referee")
    if ref.get("known") and ref.get("effect") is not None:
        change = np.exp(ref["effect"]) - 1
        st.write(f"{ref['name']}: about {abs(change):.0%} {'more' if change > 0 else 'fewer'} "
                 "yellow cards than an average referee, other things equal.")
    elif row["league"] == "LaLiga":
        st.write("La Liga referees are named after our lock, so the forecast averages over "
                 "referees.")
    else:
        st.write("Not known at lock: the forecast averages over EPL referees.")

intervals = json.loads(row["intervals"]) if isinstance(row["intervals"], str) else {}
if intervals:
    st.subheader("Uncertainty")
    names = {"p_home": f"{home} win", "p_draw": "Draw", "p_away": f"{away} win",
             "p_over_2_5": "Over 2.5 goals", "p_btts": "Both teams score"}
    st.dataframe(pd.DataFrame([{"Market": names[k], "Forecast": row[k], "80% range, low": v[0],
                                "80% range, high": v[1]} for k, v in intervals.items()
                               if k in names]), hide_index=True, column_config={
        c: st.column_config.NumberColumn(c, format="percent")
        for c in ("Forecast", "80% range, low", "80% range, high")})
    lib.caption("How sure the model is about each chance.",
                "The model has a range of plausible club ratings, not one value. Across that "
                "range, the chance falls between the low and high values 80% of the time. A "
                "wide range means the model has less to go on, for example early in the "
                "season or for a promoted club.")
