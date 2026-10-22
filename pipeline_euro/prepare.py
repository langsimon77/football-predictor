"""Resolve club names across sources, cross-check this season's European results and fixtures
(fixtures.py), and write the match table the models read (df.pkl) and the fixtures to forecast."""
import json

import pandas as pd

import data
import fixtures
import paths

df, R = data.load()
chk = fixtures.collect(R, paths.RUN_DATE)
# This season's league-phase results: drop any the two sources disagree on, add any only
# Wikipedia has (its date taken from the matchday).
bad = {tuple(c["key"]) for c in chk["report"]["results"]["conflicts"]}
cur = df[df.comp.isin(["UEL", "UECL"]) & (df.date >= "2026-07-01")]
drop = [i for i, r in cur.iterrows() if (r.comp, r.H, r.A) in bad]
have = {(r.comp, r.H, r.A) for r in cur.itertuples()}
add = []
for r in chk["results"]:
    k = (r["comp"], R(r["home"], r["hcc"]), R(r["away"], r["acc"]))
    if k not in have and r["date"] <= paths.CUTOFF:
        add.append(dict(date=r["date"], home=r["home"], away=r["away"], hcc=r["hcc"], acc=r["acc"], hg=r["hg"], ag=r["ag"], comp=r["comp"],
                        src="wikipedia", H=k[1], A=k[2], eur=1, main=1))
df = df.drop(index=drop)
if add:
    extra = pd.DataFrame(add)
    extra["t"] = pd.to_datetime(extra.date)
    df = pd.concat([df, extra], ignore_index=True).sort_values("date").reset_index(drop=True)
df.to_pickle(str(paths.WORK / "df.pkl"))
(paths.WORK / "fixtures.json").write_text(json.dumps(chk["upcoming"], indent=0), encoding="utf-8")
(paths.OUT / "fixtures_check.json").write_text(json.dumps(chk["report"], indent=1), encoding="utf-8")
print(len(df), "matches;", int(df.main.sum()), "in the three UEFA competitions; last", df.date.max())
print("cross-check:", json.dumps(chk["report"]))
