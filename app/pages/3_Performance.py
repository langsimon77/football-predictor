"""Performance tracker (spec S9, page 4)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lib

lib.setup("Performance")
lib.updated_line()
perf = lib.table("performance.parquet")
backtest = lib.table("backtest.parquet")
PROBS = ["p_home", "p_draw", "p_away"]
MAIN = ["dc_bayes_v1", "elo_v0", "base_rates", "market_friday", "market_close"]
COLOURS = {"dc_bayes_v1": lib.HOME, "elo_v0": "#009E73", "base_rates": "#999999",
           "market_friday": "#E69F00", "market_close": lib.AWAY, "stack_v1": "#CC79A7"}


def summary(frame: pd.DataFrame, model_col: str = "model_name") -> pd.DataFrame:
    rows = []
    for model, g in frame.groupby(model_col):
        p, y = g[PROBS].to_numpy(dtype=float), g["outcome"].to_numpy(dtype=int)
        rows.append({"Model": lib.MODEL_NAMES.get(str(model), str(model)), "Matches": len(g),
                     "RPS": lib.rps(p, y).mean(), "Log loss": lib.log_loss(p, y).mean(),
                     "Brier": lib.brier(p, y).mean(),
                     "Top pick right": (p.argmax(1) == y).mean()})
    return pd.DataFrame(rows).sort_values("RPS")


def calibration(p: np.ndarray, y: np.ndarray, label: str) -> None:
    pts = lib.calibration_points(p, y)
    fig = go.Figure()
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(dash="dot", color="#999999"),
                    showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=pts["forecast"], y=pts["observed"], mode="lines+markers",
                    marker=dict(color=lib.HOME, size=6 + 10 * pts["n"] / pts["n"].max()),
                    name=label, hovertemplate="said %{x:.0%}, happened %{y:.0%}<extra></extra>")
    fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0),
                      xaxis=dict(title="Forecast chance", tickformat=".0%", range=[0, 1]),
                      yaxis=dict(title="How often it happened", tickformat=".0%", range=[0, 1]))
    lib.chart(fig)


st.subheader("Live record, 2026/27")
live = perf[perf["model_name"].isin(MAIN + ["stack_v1"])] if len(perf) else perf
if live.empty:
    st.info("No locked forecast has been scored yet. The first locks are on Thu 8 Oct; "
            "results arrive about three hours after each final whistle. Until then, the "
            "backtest below shows what to expect.")
else:
    common = set.intersection(*(set(g["match_id"]) for _, g in live.groupby("model_name")
                                if _ in ("dc_bayes_v1", "elo_v0", "base_rates")))
    both = live[live["match_id"].isin(common)]
    st.dataframe(summary(both), hide_index=True, column_config={
        "Top pick right": st.column_config.NumberColumn(format="percent"),
        "RPS": st.column_config.NumberColumn(format="%.4f"),
        "Log loss": st.column_config.NumberColumn(format="%.4f"),
        "Brier": st.column_config.NumberColumn(format="%.4f")})
    lib.caption("Scores for home, draw, away over every scored match; lower is better.",
                "RPS (ranked probability score) rewards putting probability near what "
                "happened: calling a draw when the home side won costs less than calling an "
                "away win. Log loss punishes confident misses hardest. Brier is the squared "
                "distance from the result. Base rates: the league's recent share of home "
                "wins, draws, and away wins. Market: bookmaker prices with the margin removed, "
                "never used as an input. Only matches every model priced are compared. "
                "Match data and odds: football-data.co.uk.")

    fig = go.Figure()
    for model, g in both.sort_values("kickoff_utc").groupby("model_name"):
        p, y = g[PROBS].to_numpy(dtype=float), g["outcome"].to_numpy(dtype=int)
        running = np.cumsum(lib.rps(p, y)) / np.arange(1, len(g) + 1)
        fig.add_scatter(x=g["kickoff_utc"], y=running, mode="lines",
                        name=lib.MODEL_NAMES.get(str(model), str(model)),
                        line=dict(color=COLOURS.get(str(model), "#666666")))
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0),
                      yaxis=dict(title="Running mean RPS"), legend=dict(orientation="h", y=-0.2))
    lib.chart(fig)
    lib.caption("Running average RPS as matches are scored; lower is better.",
                "Early on, a few surprising results swing these lines a lot. Differences "
                "between models smaller than about 0.01 need a full season to mean anything.")

    rounds = []
    for (rnd, model), g in both.groupby(["round", "model_name"]):
        p, y = g[PROBS].to_numpy(dtype=float), g["outcome"].to_numpy(dtype=int)
        rounds.append({"round": rnd, "model": lib.MODEL_NAMES.get(str(model), str(model)),
                       "rps": lib.rps(p, y).mean(), "n": len(g)})
    if rounds:
        r = pd.DataFrame(rounds)
        fig = go.Figure()
        for model, g in r.groupby("model"):
            fig.add_bar(x=g["round"], y=g["rps"], name=model)
        fig.update_layout(barmode="group", height=300, margin=dict(l=0, r=0, t=10, b=0),
                          yaxis=dict(title="Mean RPS"), legend=dict(orientation="h", y=-0.3))
        lib.chart(fig)
        lib.caption("Mean RPS per gameweek; lower is better.",
                    "One bar per model per round. A single round has about 10 matches per "
                    "league, far too few to judge a model on its own.")

    primary = perf[perf["model_name"] == "dc_bayes_v1"].copy()
    if len(primary):
        calibration(primary[PROBS].to_numpy(dtype=float), primary["outcome"].to_numpy(int),
                    "Bayesian")
        lib.caption("Forecast chances against how often things happened; the dotted line is "
                    "perfect.", "Every home, draw, and away chance is grouped with others of "
                    "similar size. Points above the line mean the model was too cautious; "
                    "below, too bold. Bigger dots hold more forecasts.")

        primary["tier"] = primary["tiers"].map(lib.tier_of)
        primary["favoured"] = primary[PROBS].max(axis=1)
        primary["hit"] = primary[PROBS].to_numpy(float).argmax(1) == primary["outcome"]
        tiers = primary[primary["tier"] != ""].groupby("tier").agg(
            Matches=("hit", "size"), Promised=("favoured", "mean"), Won=("hit", "mean"))
        if len(tiers):
            st.dataframe(tiers.reindex([t for t in ("High", "Medium", "Low") if t in tiers.index]),
                         column_config={c: st.column_config.NumberColumn(c, format="percent")
                                        for c in ("Promised", "Won")})
            lib.caption("How often the favourite won in each confidence tier.",
                        "Promised: the average top chance in the tier. Won: how often that "
                        "outcome happened. A good tier system shows clearly different win "
                        "rates, with Won close to Promised in each tier.")

        p, y = primary[PROBS].to_numpy(float), primary["outcome"].to_numpy(int)
        primary["surprise"] = lib.log_loss(p, y)

        def causes(row: pd.Series) -> str:
            tags = []
            if (row.get("home_reds") or 0) + (row.get("away_reds") or 0) > 0:
                tags.append("red card")
            if isinstance(row["unanswered_questions"], str) and \
                    json.loads(row["unanswered_questions"]):
                tags.append("news question unanswered")
            if isinstance(row["news_adjustments"], str) and json.loads(row["news_adjustments"]):
                tags.append("news applied")
            if np.exp(-row["surprise"]) < 0.15:
                tags.append("upset (under 15%)")
            return ", ".join(tags) or "none tagged"

        misses = primary.sort_values("surprise", ascending=False).head(10)
        st.dataframe(pd.DataFrame({
            "Match": misses["home_id"] + " v " + misses["away_id"],
            "Score": misses["home_goals"].astype(int).astype(str) + "-"
            + misses["away_goals"].astype(int).astype(str),
            "Chance given to the result": np.exp(-misses["surprise"]),
            "Tagged causes": misses.apply(causes, axis=1)}), hide_index=True,
            column_config={"Chance given to the result":
                           st.column_config.NumberColumn(format="percent")})
        lib.caption("The ten results the model found most surprising, with objective causes.",
                    "Causes are tagged automatically from facts, not judgement: a red card, "
                    "an unanswered news question, news applied, or a result the model gave "
                    "under 15%. Whether the model itself is wrong is judged over many matches "
                    "(the calibration chart), never from one (PRD item 12).")

stack_file = lib.REPO / "data" / "stacking" / "stack_1x2.json"
if stack_file.exists():
    st.subheader("Ensemble weights")
    stack = json.loads(stack_file.read_text(encoding="utf-8"))
    w = pd.DataFrame({"model": stack["models"], "weight": stack["weights"]})
    fig = go.Figure(go.Bar(x=w["weight"], y=w["model"], orientation="h", marker_color=lib.HOME,
                           text=[f"{v:.0%}" for v in w["weight"]], textposition="outside"))
    fig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0),
                      xaxis=dict(tickformat=".0%", range=[0, 0.6]))
    lib.chart(fig)
    lib.caption("Weight of each model in the shadow stack; the published forecast is the "
                "Bayesian model.", "Fitted on the 2021/22 and 2022/23 backtest with a 5% "
                "floor per model. From Phase 7 the weekly run may move each weight by at most "
                "10 points a week, and only after 60 scored live matches.")

if len(backtest):
    st.subheader("Backtest, 2023/24 to 2025/26")
    models = [c[:-5] for c in backtest.columns if c.endswith("_home")]
    long = pd.concat([pd.DataFrame({"model_name": m, "outcome": backtest["outcome"],
                                    "p_home": backtest[f"{m}_home"],
                                    "p_draw": backtest[f"{m}_draw"],
                                    "p_away": backtest[f"{m}_away"]}).dropna()
                      for m in models], ignore_index=True)
    long["model_name"] = long["model_name"].replace({
        "bdc": "dc_bayes_v1", "elo": "elo_v0", "dc": "dc_mle_v0", "base": "base_rates",
        "stack": "stack_v1", "mkt_avg_pre": "market_friday", "mkt_sharp": "market_close"})
    st.dataframe(summary(long), hide_index=True, column_config={
        "Top pick right": st.column_config.NumberColumn(format="percent"),
        "RPS": st.column_config.NumberColumn(format="%.4f"),
        "Log loss": st.column_config.NumberColumn(format="%.4f"),
        "Brier": st.column_config.NumberColumn(format="%.4f")})
    lib.caption("How each model scored on three past seasons, forecast as if live.",
                "Walk-forward: every forecast used only what was known at its lock time. "
                "Settings were chosen on 2021/22 and 2022/23 and these three seasons were "
                "scored once. Full report: reports/backtest_phase4.md.")
    calibration(backtest[["bdc_home", "bdc_draw", "bdc_away"]].to_numpy(float),
                backtest["outcome"].to_numpy(int), "Bayesian, backtest")
    lib.caption("Backtest calibration of the Bayesian model; the dotted line is perfect.",
                "Points above the line at the top end show the known timidity: strong "
                "favourites won more often than the model said (see Methods, chapter 2.8).")
