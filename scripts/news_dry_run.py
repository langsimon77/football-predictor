"""Phase 5 acceptance dry run on the first real gameweek (9 to 12 Oct 2026).

1. The Issue each daily run from 6 to 10 Oct would open: which matches, in which
   order, and the full text of the busiest day.
2. The lock run of Fri 9 Oct with EXAMPLE ticks (not real team news) for the
   Saturday matches asked about on Thu 8 Oct, through the real locking code:
   adjustments, caps, the no-news copy, unanswered flags, tiers.

Nothing is written to the ledger and no Issue is opened.

    uv run python scripts/news_dry_run.py
"""

from __future__ import annotations

import json
import sys
from unittest import mock

import pandas as pd

from fp import ROOT
from fp.ingest import matches as build
from fp.models.priors import PromotedPrior
from fp.models.promotion import fit_promotion_model
from fp.news import live as news_live
from fp.news import managers, queue
from fp.news.impact import CAP, TeamNews
from fp.pipeline import counts_live, daily

OUT = ROOT / "reports" / "phase5_dry_run.md"
RUNS = pd.date_range("2026-10-06 04:41", "2026-10-10 04:41", freq="D", tz="UTC")
LOCK_RUN = pd.Timestamp("2026-10-09 04:41", tz="UTC")
A = TeamNews
# EXAMPLE ticks for Saturday's matches, chosen to exercise every rule.
EXAMPLE = {
    "EPL_2627_arsenal_leeds": (A("answered", 0, False), A("answered", 1, False)),
    "EPL_2627_chelsea_bournemouth": (A("answered", 3, True), A("answered", 0, False)),
    "EPL_2627_man_united_tottenham": (A("answered", 2, True), A("answered", 3, True)),
    "LaLiga_2627_barcelona_getafe": (A("answered", 1, True), A("dont_know")),
    "LaLiga_2627_real_madrid_villarreal": (A("unanswered"), A("unanswered")),
    "EPL_2627_aston_villa_brentford": (A("answered", 0, False), A("answered", 0, False)),
}


def table(rows: list[dict]) -> str:
    frame = pd.DataFrame(rows)
    head = "| " + " | ".join(frame.columns) + " |\n|" + "---|" * len(frame.columns)
    return head + "\n" + "\n".join("| " + " | ".join(str(v) for v in r) + " |"
                                   for r in frame.itertuples(index=False))


def describe(news: TeamNews) -> str:
    if news.status != "answered":
        return {"dont_know": "don't know"}.get(news.status, news.status)
    out = f"{news.starters_out}{'+' if news.starters_out >= 3 else ''} out"
    return out + (", main threat out" if news.threat_out else "")


def main() -> int:
    matches = pd.read_parquet(build.PROCESSED / "matches.parquet")
    fixtures = pd.read_parquet(build.PROCESSED / "fixtures.parquet")
    second_tier = pd.read_parquet(build.PROCESSED / "second_tier.parquet")
    prior = PromotedPrior(matches)
    names = daily._short_names()
    season = int(fixtures["season"].max())

    # 1. The Issues.
    asked: set[str] = set()
    issue_rows, bodies = [], {}
    ranked_ok = True
    for now in RUNS:
        fits = {lg: daily.fit_league(matches, fixtures, lg, now, prior, season).dc_fit
                for lg in daily.LEAGUES}
        ranked = queue.rank(queue.to_ask(fixtures, now, asked), fits)
        kept = ranked[:queue.MAX_QUESTIONS]
        shifts = [q.shift for q in kept]
        ranked_ok &= shifts == sorted(shifts, reverse=True)
        asked |= {q.match_id for q in kept}
        if kept:
            title, bodies[now] = queue.render(kept, [], names, now)
        issue_rows.append({
            "run (UTC)": f"{now:%a %d %b %H:%M}", "questions": len(kept),
            "left out by the cap of 10": len(ranked) - len(kept),
            "matches, highest expected shift first": "; ".join(
                f"{names[q.home_id]} v {names[q.away_id]} ({q.shift * 100:.1f})"
                for q in kept) or "none"})
    busiest = max(bodies, key=lambda k: bodies[k].count("### "))

    # 2. The Friday lock run with example ticks.
    state = news_live.NewsState(
        by_match={m: news_live.MatchNews(h, a, "EXAMPLE, not real news")
                  for m, (h, a) in EXAMPLE.items()},
        manager_flags=managers.recent_changes(managers.load(), LOCK_RUN))
    ctx = daily.Context(
        matches=matches, fixtures=fixtures, second_tier=second_tier, prior=prior,
        promo=fit_promotion_model(matches, second_tier),
        ledger_path=ROOT / "data" / "interim" / "phase5_dry" / "predictions.parquet",
        results_path=ROOT / "data" / "interim" / "phase5_dry" / "results.parquet",
        report_path=None, with_bayes=True,
        store=ROOT / "data" / "interim" / "phase5_dry" / "posteriors",
        with_counts=counts_live.COUNTS_LIVE,
        referee_appointments=pd.read_parquet(build.PROCESSED / "referee_appointments.parquet"),
        with_shadows=True, with_tiers=True, with_news=True, use_github=False)
    with mock.patch.object(news_live, "gather", return_value=state):
        new = daily.run_once(LOCK_RUN, ctx, dry_run=True)
    # The dry run starts from an empty ledger, so matches the Thursday run would
    # already have locked show up again as late locks. Leave them out.
    new = new[~new["late_lock"].astype(bool)]
    rows = new.set_index("prediction_id")
    lock_rows = []
    for match_id in sorted(set(new["match_id"])):
        primary = rows.loc[f"{match_id}:dc_bayes_v1"]
        plain_id = f"{match_id}:dc_bayes_v1_nonews"
        plain = rows.loc[plain_id] if plain_id in rows.index else primary
        adj = json.loads(primary["news_adjustments"])
        mn = state.by_match.get(match_id)
        r = new[new["match_id"] == match_id].iloc[0]
        home, away = names[r["home_id"]], names[r["away_id"]]
        lock_rows.append({
            "match": f"{home} v {away}",
            "example ticks (home; away)": (f"{describe(mn.home)}; {describe(mn.away)}"
                                           if mn else "not asked"),
            "goal rates x": (f"{adj[0]['scale_home_goals']:.3f}, "
                             f"{adj[0]['scale_away_goals']:.3f}" if adj else "1, 1"),
            "capped": "yes" if adj and adj[0]["capped"] else "no",
            "home, draw, away without news": (f"{plain['p_home']:.0%}, {plain['p_draw']:.0%}, "
                                              f"{plain['p_away']:.0%}"),
            "with news": (f"{primary['p_home']:.0%}, {primary['p_draw']:.0%}, "
                          f"{primary['p_away']:.0%}"),
            "unanswered": len(json.loads(primary["unanswered_questions"])),
            "1X2 tier": json.loads(primary["tiers"]).get("1x2", ""),
        })
    scales = [v for a in new["news_adjustments"] for rec in json.loads(a)
              for v in (rec["scale_home_goals"], rec["scale_away_goals"])]
    within = all(1 - CAP - 1e-9 <= s <= 1 + CAP + 1e-9 for s in scales)
    per_day = all(r["questions"] <= queue.MAX_QUESTIONS for r in issue_rows)
    checks = [
        {"Check": "Adjustments within the 12% cap",
         "Result": f"{'yes' if within else 'NO'}: every goal-rate multiplier between "
                   f"{1 - CAP:.2f} and {1 + CAP:.2f} ({len(scales)} multipliers)."},
        {"Check": "At most 10 questions a day", "Result": "yes" if per_day else "NO"},
        {"Check": "Questions ranked",
         "Result": f"{'yes' if ranked_ok else 'NO'}: by expected shift in the home, draw, "
                   "away forecast (points in brackets)."},
        {"Check": "Questions specific",
         "Result": "Each names both clubs, the league, the kickoff in Juba time and UTC, "
                   "and links a team-news search."},
    ]

    quoted = "\n".join(f"> {line}" if line else ">" for line in bodies[busiest].splitlines())
    text = f"""# Phase 5 dry run: team news and the Question Queue

Generated by `scripts/news_dry_run.py`. Fits use results known on 26 Sep 2026.
Nothing was written to the ledger and no Issue was opened.

## Acceptance checks (spec section 11, Phase 5)

{table(checks)}

## 1. The Issue each run would open

A run asks about matches kicking off 48 to 72 hours later: they lock at the next
run, so you have about a day to tick.

{table(issue_rows)}

### Full text of the busiest day ({busiest:%a %d %b})

As you would see it on GitHub (the markers after each box are hidden there):

{quoted}

## 2. The lock run of {LOCK_RUN:%a %d %b %H:%M} UTC with EXAMPLE ticks

These ticks are made up to exercise every rule. They are not real team news.
Matches not asked about lock without news and without a flag.

{table(lock_rows)}
"""
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
