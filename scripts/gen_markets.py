"""Generate the market maps from data/markets/markets.json (the single definition).

    python scripts/gen_markets.py [--js PATH]

writes src/fp/markets_gen.py and, with --js, the Model Lab's markets module. Settle rules
are data ([stat, op, value]), evaluated the same way in Python and JavaScript; no eval.
"""
from __future__ import annotations

import argparse
import json
import math
import pprint
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "data" / "markets" / "markets.json"
TEMPLATES = ROOT / "scripts" / "templates"
PY_OUT = ROOT / "src" / "fp" / "markets_gen.py"


def _num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def _rule(r: list, line: float | None) -> list:
    return [r[0], r[1], float(line) if r[2] == "{line}" else r[2]]


def expand(spec: dict) -> dict[str, dict]:
    """One entry per concrete code, lines filled in."""
    out: dict[str, dict] = {}
    for m in spec["markets"]:
        for line in m.get("lines") or [None]:
            sub = {"home": "{home}", "away": "{away}"}
            if line is not None:
                below = math.floor(line)
                sub.update(line=_num(line), above=str(math.ceil(line)), below=str(below),
                           s="" if below == 1 else "s")
            market = m["market"]
            if isinstance(market, dict):
                market = market.get(_num(line), market["*"])
            e = {"code": m["code"].format(**sub), "family": m["family"], "market": market,
                 "label": m["label"].format(**sub),
                 "book": [m["book"][0].format(**sub), m["book"][1]],
                 "win": _rule(m["win"], line)}
            if "call" in m:
                e["call"] = m["call"].format(**sub)
            if "void" in m:
                e["void"] = _rule(m["void"], line)
            published = [float(x) for x in m.get("published", [])]
            e["published"] = line is None or float(line) in published
            if line is not None:
                e["line"] = float(line)
            if e["code"] in out:
                raise SystemExit(f"duplicate code {e['code']}")
            out[e["code"]] = e
    for e in out.values():
        for r in [e["win"]] + ([e["void"]] if "void" in e else []):
            if r[0] not in spec["stats"] or r[1] not in spec["ops"]:
                raise SystemExit(f"bad rule in {e['code']}: {r}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--js", type=Path, default=None, help="also write the Model Lab markets module")
    args = ap.parse_args(argv)
    m = expand(json.loads(SPEC.read_text(encoding="utf-8")))
    py = (TEMPLATES / "markets_gen.py.tmpl").read_text(encoding="utf-8")
    PY_OUT.write_text(py.replace("__MARKETS__", pprint.pformat(m, width=95, sort_dicts=False)),
                      encoding="utf-8")
    print(f"wrote {PY_OUT.relative_to(ROOT)} ({len(m)} codes)")
    if args.js:
        js = (TEMPLATES / "markets.gen.js.tmpl").read_text(encoding="utf-8")
        blob = json.dumps(m, separators=(",", ":"), ensure_ascii=False)
        args.js.write_text(js.replace("__MARKETS__", blob), encoding="utf-8")
        print(f"wrote {args.js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
