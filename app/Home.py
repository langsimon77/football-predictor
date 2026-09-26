"""Fixtures: the home page (spec S9, page 1)."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lib

lib.setup("Fixtures")
lib.updated_line()
fx = lib.table("fixtures.parquet")
if fx.empty:
    st.info("No upcoming matches in the published data.")
    st.stop()

MARKETS = {
    "Home, draw, away": None, "Over 2.5 goals": "p_over_2_5", "Both teams score": "p_btts",
    "Over 9.5 corners": "p_corners_over_9_5", "Over 4.5 yellows": "p_yellows_over_4_5",
}
TIER_KEYS = {"Home, draw, away": "1x2", "Over 2.5 goals": "over_2_5", "Both teams score": "btts",
             "Over 9.5 corners": "corners_over_9_5", "Over 4.5 yellows": "yellows_over_4_5"}

market = st.selectbox("Market", list(MARKETS))
with st.expander("Filters and time zone"):
    leagues = st.multiselect("League", ["EPL", "LaLiga"], default=["EPL", "LaLiga"],
                             format_func=lib.league_name)
    utc = st.toggle("Show kickoff times in UTC (default: Juba time, UTC+2)")
    fx["kickoff"] = lib.juba(fx["kickoff_utc"], utc)
    fx["day"] = fx["kickoff"].dt.strftime("%a %d %b")
    days = list(dict.fromkeys(fx.sort_values("kickoff_utc")["day"]))
    chosen_days = st.multiselect("Day", days, default=days)
    fx["tier"] = fx["tiers"].map(lambda s: lib.tier_of(s, TIER_KEYS[market]))
    tiers = st.multiselect("Tier", ["High", "Medium", "Low"],
                           default=["High", "Medium", "Low"])
view = fx[fx["league"].isin(leagues) & fx["day"].isin(chosen_days)
          & (fx["tier"].isin(tiers) | (fx["tier"] == ""))].sort_values("kickoff_utc")
if view.empty:
    st.info("No matches match these filters.")
    st.stop()

view["match"] = view["home_name"] + " v " + view["away_name"]
view["label"] = view["kickoff"].dt.strftime("%a %H:%M") + " " + view["match"]


def news_note(row: pd.Series) -> str:
    adj = json.loads(row["news_adjustments"]) if isinstance(row["news_adjustments"], str) else []
    unanswered = (json.loads(row["unanswered_questions"])
                  if isinstance(row["unanswered_questions"], str) else [])
    moved = any(abs(r["scale_home_goals"] - 1) > 0.004 or abs(r["scale_away_goals"] - 1) > 0.004
                for r in adj)
    return "adjusted" if moved else "unanswered" if unanswered else ""


view["news"] = view.apply(news_note, axis=1)
view["status"] = view["locked"].map({True: "Locked", False: "Provisional"})

if MARKETS[market] is None:
    fig = go.Figure()
    order = view["label"].tolist()[::-1]
    for col, name, colour in (("p_home", "Home win", lib.HOME), ("p_draw", "Draw", lib.DRAW),
                              ("p_away", "Away win", lib.AWAY)):
        values = view.set_index("label").loc[order, col]
        fig.add_bar(y=order, x=values, name=name, orientation="h", marker_color=colour,
                    text=[f"{v:.0%}" if v >= 0.15 else "" for v in values],
                    textposition="inside", textangle=0, insidetextanchor="middle",
                    hovertemplate="%{y}: %{x:.0%}<extra>" + name + "</extra>")
    fig.update_layout(barmode="stack", height=70 + 30 * len(view),
                      margin=dict(l=0, r=0, t=30, b=0),
                      xaxis=dict(tickformat=".0%", range=[0, 1], showticklabels=False),
                      legend=dict(orientation="h", y=1.0, yanchor="bottom",
                                  traceorder="normal"),
                      yaxis=dict(automargin=True, tickfont=dict(size=11)))
    lib.chart(fig)
    lib.caption("Each bar splits one match into the chances of a home win, a draw, and an "
                "away win.",
                "The published model is a Bayesian Dixon-Coles model: it rates every club's "
                "attack and defence from past results and shots on target, weights recent "
                "matches more, and turns the two scoring rates into a table of scorelines. "
                "Summing that table gives home, draw, and away. Locked forecasts were fixed "
                "24 to 48 hours before kickoff and never change; provisional ones update "
                "daily until they lock. See Methods, chapter 2.")
else:
    col = MARKETS[market]
    fig = go.Figure(go.Bar(y=view["label"][::-1], x=view[col][::-1], orientation="h",
                           marker_color=lib.HOME, text=[f"{v:.0%}" for v in view[col][::-1]],
                           textposition="inside"))
    fig.update_layout(height=90 + 34 * len(view), margin=dict(l=0, r=0, t=10, b=0),
                      xaxis=dict(tickformat=".0%", range=[0, 1]), yaxis=dict(automargin=True))
    lib.chart(fig)
    lib.caption(f"Chance of {market.lower()} in each match.",
                "Goals markets come from the Bayesian scoreline table. Corners come from a "
                "Poisson model of the match total; yellow cards from a negative binomial "
                "model with a referee effect in the EPL. See Methods, chapter 3b.")

table = pd.DataFrame({
    "Kickoff": view["kickoff"].dt.strftime("%a %d %b %H:%M") + (" UTC" if utc else ""),
    "League": view["league"].map(lib.league_name), "Match": view["match"],
    "Home": view["p_home"], "Draw": view["p_draw"], "Away": view["p_away"],
    "Exp. goals": view["exp_goals_home"].map("{:.1f}".format) + " to "
    + view["exp_goals_away"].map("{:.1f}".format),
    "Exp. corners": (view["exp_corners_home"] + view["exp_corners_away"]).round(1),
    "Exp. yellows": view["exp_yellows"].round(1),
    "Tier": view["tier"], "News": view["news"], "Status": view["status"],
})
st.dataframe(table, hide_index=True, column_config={
    c: st.column_config.ProgressColumn(c, format="percent", min_value=0, max_value=1)
    for c in ("Home", "Draw", "Away")})
lib.caption("Every match in view, sortable by any column (tap a header).",
            "Tier: how far to trust the forecast for the chosen market (High, Medium, Low), "
            "set from past seasons so each tier's record is clearly different. News: "
            "\"adjusted\" when your answers moved the forecast, \"unanswered\" when a "
            "question went unanswered (the tier is then capped at Medium). See Methods, "
            "chapters 4 and 5.")
st.download_button("Download as CSV", table.to_csv(index=False).encode("utf-8"),
                   file_name="fixtures.csv", mime="text/csv")
