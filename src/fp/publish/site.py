"""The static Fixtures page for GitHub Pages (PRD Q4: fast on a phone).

One self-contained HTML file (inline CSS and a few lines of JavaScript, no
downloads), plus fixtures.csv. Light and dark follow the phone's setting.
Colours are Okabe-Ito (colour-blind safe), and every coloured item also carries
text. Works without JavaScript; the script only adds filters, sorting, and the
UTC toggle.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

from fp import ROOT

SITE = ROOT / "site"
JUBA = "Africa/Juba"
# Streamlit Community Cloud, deployed by Lang on 26 Sep 2026.
DASHBOARD_URL = "https://football-predictor-hvplshfcfv7vsqqkaplmbq.streamlit.app/"

CSS = """
:root{--bg:#fff;--fg:#1b1b1b;--muted:#5f5f5f;--line:#e3e3e3;--card:#fafafa;
--home:#0072B2;--draw:#8c8c8c;--away:#D55E00;--hi:#009E73;--md:#E69F00;--lo:#CC79A7}
@media (prefers-color-scheme:dark){:root{--bg:#111;--fg:#ececec;--muted:#a8a8a8;
--line:#2c2c2c;--card:#1a1a1a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:760px;margin:auto;padding:12px 16px 40px}h1{font-size:1.35rem;margin:.4rem 0}
h2{font-size:1rem;margin:1.2rem 0 .4rem;color:var(--muted)}.cap{color:var(--muted);margin:.2rem 0}
.ctl{display:flex;flex-wrap:wrap;gap:6px;margin:.6rem 0}.ctl button,.ctl a{font:inherit;
padding:4px 10px;border:1px solid var(--line);border-radius:14px;background:var(--card);
color:var(--fg);text-decoration:none;cursor:pointer}.ctl .on{border-color:var(--fg);font-weight:600}
article{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 10px;
margin:6px 0}.top{display:flex;flex-wrap:wrap;gap:6px;align-items:baseline}
.t{font-variant-numeric:tabular-nums;color:var(--muted)}.lg{font-size:.8rem;color:var(--muted)}
.b{margin-left:auto;display:flex;gap:4px}.tag{font-size:.75rem;padding:1px 7px;border-radius:9px;
border:1px solid var(--line)}.High{background:var(--hi);color:#fff;border:0}
.Medium{background:var(--md);color:#111;border:0}.Low{background:var(--lo);color:#111;border:0}
.bar{display:flex;height:22px;border-radius:5px;overflow:hidden;margin:6px 0 4px;font-size:.78rem}
.bar span{display:flex;align-items:center;justify-content:center;color:#fff;min-width:0;
white-space:nowrap;overflow:hidden}.h{background:var(--home)}.d{background:var(--draw)}
.a{background:var(--away)}.n{font-size:.85rem;color:var(--muted)}.nw{color:var(--fg)}
footer{margin-top:1.5rem;font-size:.8rem;color:var(--muted)}
"""

JS = """
const q=s=>[...document.querySelectorAll(s)];let lg='all',tz='juba';
function show(){q('article').forEach(a=>{a.hidden=lg!=='all'&&a.dataset.lg!==lg});
q('h2').forEach(h=>{const s=h.nextElementSibling;h.hidden=!q('#'+s.id+' article').some(
a=>!a.hidden)});}
q('[data-lgb]').forEach(b=>b.onclick=()=>{lg=b.dataset.lgb;q('[data-lgb]').forEach(x=>
x.classList.toggle('on',x===b));show()});
q('[data-tzb]').forEach(b=>b.onclick=()=>{tz=b.dataset.tzb;q('[data-tzb]').forEach(x=>
x.classList.toggle('on',x===b));q('.t').forEach(t=>{const d=new Date(t.dataset.utc);
t.textContent=d.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',
timeZone:tz==='utc'?'UTC':'Africa/Juba'})+(tz==='utc'?' UTC':'')})});
q('[data-sort]').forEach(b=>b.onclick=()=>{const k=b.dataset.sort;q('[data-sort]').forEach(x=>
x.classList.toggle('on',x===b));q('section').forEach(s=>{const arts=q('#'+s.id+' article');
arts.sort((x,y)=>k==='time'?x.dataset.ko.localeCompare(y.dataset.ko):y.dataset[k]-x.dataset[k]);
arts.forEach(a=>s.appendChild(a))})});
"""

TIER_RANK = {"High": 3, "Medium": 2, "Low": 1}


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _news(row: pd.Series) -> str:
    adj = json.loads(row["news_adjustments"]) if isinstance(row["news_adjustments"], str) else []
    unanswered = (json.loads(row["unanswered_questions"])
                  if isinstance(row["unanswered_questions"], str) else [])
    parts = []
    for rec in adj:
        for side, key in (("home", "scale_home_goals"), ("away", "scale_away_goals")):
            change = rec[key] - 1
            if abs(change) >= 0.005:
                name = row["home_name"] if side == "home" else row["away_name"]
                sign = "+" if change > 0 else "−"
                parts.append(f"{html.escape(str(name))} goals {sign}{abs(change) * 100:.0f}%")
    if unanswered:
        parts.append("question unanswered")
    return "; ".join(parts)


def card(row: pd.Series) -> str:
    kick = pd.Timestamp(row["kickoff_utc"])
    tiers = json.loads(row["tiers"]) if isinstance(row["tiers"], str) else {}
    tier = tiers.get("1x2")
    league = "La Liga" if row["league"] == "LaLiga" else row["league"]
    status = "Locked" if row["locked"] else "Provisional"
    goals = f"Goals {row['exp_goals_home']:.1f} to {row['exp_goals_away']:.1f}"
    extra = [goals, f"Over 2.5: {_pct(row['p_over_2_5'])}"]
    if pd.notna(row["exp_corners_home"]):
        extra.append(f"Corners {row['exp_corners_home']:.1f} to {row['exp_corners_away']:.1f}")
    if pd.notna(row["exp_yellows"]):
        extra.append(f"Yellows {row['exp_yellows']:.1f}")
    news = _news(row)
    bar = "".join(
        f'<span class="{c}" style="width:{p * 100:.1f}%" title="{label} {_pct(p)}">'
        f"{_pct(p) if p >= 0.12 else ''}</span>"
        for c, label, p in (("h", "Home", row["p_home"]), ("d", "Draw", row["p_draw"]),
                            ("a", "Away", row["p_away"])))
    badges = f'<span class="tag">{status}</span>' + (
        f'<span class="tag {tier}" title="Confidence tier, 1X2">{tier}</span>' if tier else "")
    return (
        f'<article data-lg="{row["league"]}" data-ko="{kick:%Y-%m-%dT%H:%M}" '
        f'data-tier="{TIER_RANK.get(tier or "", 0)}" data-home="{row["p_home"]:.3f}">'
        f'<div class="top"><span class="t" data-utc="{kick:%Y-%m-%dT%H:%M:00Z}">'
        f"{kick.tz_convert(JUBA):%H:%M}</span><b>{html.escape(str(row['home_name']))}</b> v "
        f"<b>{html.escape(str(row['away_name']))}</b><span class=\"lg\">{league}</span>"
        f'<span class="b">{badges}</span></div><div class="bar" role="img" '
        f'aria-label="Home {_pct(row["p_home"])}, draw {_pct(row["p_draw"])}, away '
        f'{_pct(row["p_away"])}">{bar}</div><div class="n">{" &middot; ".join(extra)}'
        + (f' &middot; <span class="nw">News: {news}</span>' if news else "")
        + "</div></article>")


def render(fixtures: pd.DataFrame, generated: pd.Timestamp) -> str:
    fx = fixtures.sort_values("kickoff_utc")
    days = []
    for day, group in fx.groupby(fx["kickoff_utc"].dt.tz_convert(JUBA).dt.date, sort=True):
        label = pd.Timestamp(day).strftime("%a %d %b")
        days.append(f'<h2>{label}</h2><section id="d{pd.Timestamp(day):%Y%m%d}">'
                    + "".join(card(r) for _, r in group.iterrows()) + "</section>")
    body = "".join(days) or "<p>No matches scheduled yet.</p>"
    link = (f' <a href="{DASHBOARD_URL}">Full dashboard</a>.' if DASHBOARD_URL else "")
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>EPL and La Liga forecasts</title>"
        f"<style>{CSS}</style></head><body><main><h1>EPL and La Liga: next matches</h1>"
        f'<p class="cap">Updated {generated.tz_convert(JUBA):%a %d %b %Y, %H:%M} Juba time. '
        "Kickoffs in Juba time (UTC+2). Locked forecasts never change; provisional ones "
        "update daily until they lock 24 to 48 hours before kickoff.</p>"
        '<p class="cap">Each bar shows the chances of a home win (blue), a draw (grey), and '
        "an away win (orange). The tier says how far to trust the home, draw, away "
        "forecast.</p>"
        '<div class="ctl"><button class="on" data-lgb="all">All</button>'
        '<button data-lgb="EPL">EPL</button><button data-lgb="LaLiga">La Liga</button>'
        '<button class="on" data-tzb="juba">Juba</button><button data-tzb="utc">UTC</button>'
        '<button class="on" data-sort="time">By time</button>'
        '<button data-sort="tier">By tier</button><button data-sort="home">By home chance'
        '</button><a href="fixtures.csv" download>CSV</a></div>'
        f"{body}<footer>Forecasts from a Bayesian Dixon-Coles model with team news from "
        "a daily question queue. Bookmaker odds are never an input. Not betting advice. "
        "Match data: football-data.co.uk; fixtures: openfootball."
        f"{link}</footer></main><script>{JS}</script></body></html>")


def write(fixtures: pd.DataFrame, generated: pd.Timestamp, out: Path = SITE,
          data_dir: Path | None = None) -> Path:
    """The page, fixtures.csv, and a copy of the dashboard files under data/, so the
    Streamlit app can read them from the same public address."""
    out.mkdir(parents=True, exist_ok=True)
    if data_dir is not None and data_dir.exists():
        (out / "data").mkdir(exist_ok=True)
        for f in data_dir.iterdir():
            if f.is_file():
                (out / "data" / f.name).write_bytes(f.read_bytes())
    page = out / "index.html"
    page.write_text(render(fixtures, generated), encoding="utf-8")
    csv = fixtures.assign(
        kickoff_juba=fixtures["kickoff_utc"].dt.tz_convert(JUBA).dt.strftime("%Y-%m-%d %H:%M"),
        tier_1x2=fixtures["tiers"].map(lambda s: json.loads(s).get("1x2", "")
                                       if isinstance(s, str) else ""))
    csv[["kickoff_juba", "league", "home_name", "away_name", "locked", "p_home", "p_draw",
         "p_away", "p_over_2_5", "p_btts", "exp_goals_home", "exp_goals_away",
         "exp_corners_home", "exp_corners_away", "exp_yellows", "tier_1x2"]].round(4).to_csv(
        out / "fixtures.csv", index=False)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return page
