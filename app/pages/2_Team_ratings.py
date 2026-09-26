"""Team ratings and the season projection (spec S9, page 3)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lib

lib.setup("Team ratings")
lib.updated_line()
ratings = lib.table("ratings.parquet")
history = lib.table("ratings_history.csv")
projection = lib.table("projection.parquet")
if ratings.empty:
    st.info("No ratings in the published data yet.")
    st.stop()

league = st.segmented_control("League", ["EPL", "LaLiga"], default="EPL",
                              format_func=lib.league_name) or "EPL"
r = ratings[ratings["league"] == league].sort_values("attack")

fig = go.Figure()
fig.add_scatter(
    x=r["defence"], y=r["attack"], mode="markers+text", text=r["team_name"],
    textposition="top center", marker=dict(color=lib.HOME, size=8),
    error_x=dict(type="data", symmetric=False, array=r["defence_hi"] - r["defence"],
                 arrayminus=r["defence"] - r["defence_lo"], color="#bbbbbb", thickness=1),
    error_y=dict(type="data", symmetric=False, array=r["attack_hi"] - r["attack"],
                 arrayminus=r["attack"] - r["attack_lo"], color="#bbbbbb", thickness=1),
    hovertemplate="%{text}<br>attack %{y:.2f}, defence %{x:.2f}<extra></extra>")
fig.add_hline(y=1, line_dash="dot", line_color="#999999")
fig.add_vline(x=1, line_dash="dot", line_color="#999999")
fig.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0),
                  xaxis=dict(title="Goals conceded vs league average (left is better)",
                             autorange="reversed"),
                  yaxis=dict(title="Goals scored vs league average"))
lib.chart(fig)
lib.caption("Every club's attack and defence today; top right is strongest, lines show "
            "80% ranges.",
            "Ratings are multiples of an average club in this league: attack 1.30 means 30% "
            "more goals than average against an average defence; defence 0.80 means 20% "
            "fewer goals conceded. They come from the Bayesian model fitted in today's run, "
            "which weights recent matches more (a half-life of about a year). The grey lines "
            "cover 80% of the model's plausible values; long lines mean less evidence, such "
            "as a promoted club early in the season.")

if len(history):
    h = history[history["league"] == league]
    names = dict(zip(ratings["team_id"], ratings["team_name"], strict=True))
    teams = st.multiselect("Clubs over time", sorted(h["team_id"].unique()),
                           default=list(r.sort_values("attack", ascending=False)["team_id"][:3]),
                           format_func=lambda t: names.get(t, t))
    if len(h["date"].unique()) < 2:
        st.caption("The history starts on the first published day; lines appear from the "
                   "second.")
    measure = st.segmented_control("Rating", ["attack", "defence"], default="attack") or "attack"
    fig = go.Figure()
    palette = [lib.HOME, lib.AWAY, "#009E73", "#CC79A7", "#56B4E9", "#E69F00"]
    for i, team in enumerate(teams):
        t = h[h["team_id"] == team].sort_values("date")
        colour = palette[i % len(palette)]
        fig.add_scatter(x=pd.concat([t["date"], t["date"][::-1]]),
                        y=pd.concat([t[f"{measure}_hi"], t[f"{measure}_lo"][::-1]]),
                        fill="toself", line=dict(width=0), fillcolor=colour, opacity=0.18,
                        showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=t["date"], y=t[measure], mode="lines+markers", name=names.get(team, team),
                        line=dict(color=colour))
    fig.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=-0.2),
                      yaxis=dict(title=f"{measure.title()} vs league average"))
    lib.chart(fig)
    lib.caption(f"{measure.title()} rating by day for the chosen clubs, with 80% bands.",
                "One point per daily run. The band is the 80% range of the model's plausible "
                "values that day. For defence, lower is better.")

if len(projection):
    st.subheader("Season projection")
    p = projection[projection["league"] == league].sort_values("mean_points", ascending=False)
    fig = go.Figure()
    for col, name, colour in (("p_title", "Title", "#009E73"), ("p_top4", "Top four", lib.HOME),
                              ("p_relegation", "Relegation", lib.AWAY)):
        fig.add_bar(y=p["team_name"][::-1], x=p[col][::-1], name=name, orientation="h",
                    marker_color=colour)
    fig.update_layout(barmode="group", height=120 + 26 * len(p), margin=dict(l=0, r=0, t=10, b=0),
                      xaxis=dict(tickformat=".0%", range=[0, 1]),
                      legend=dict(orientation="h", y=-0.06), yaxis=dict(automargin=True))
    lib.chart(fig)
    lib.caption("Chances of winning the league, finishing in the top four, and going down.",
                "From 10,000 simulations of every remaining match. Each simulation draws one "
                "plausible set of ratings from the model, plays the matches with random "
                "goals, and adds the points to the current table. Ties are split by goal "
                "difference, then goals scored (the EPL rule; La Liga uses head to head "
                "first, which this ignores).")
    st.dataframe(pd.DataFrame({
        "Club": p["team_name"], "Played": p["played"], "Points now": p["points"],
        "Expected points": p["mean_points"], "Expected position": p["mean_position"],
        "Title": p["p_title"], "Top four": p["p_top4"], "Relegation": p["p_relegation"]}),
        hide_index=True, column_config={c: st.column_config.NumberColumn(c, format="percent")
                                        for c in ("Title", "Top four", "Relegation")})
