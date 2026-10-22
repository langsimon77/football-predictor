"""Download the four public sources the Europe pipeline is built from (all free):

- openfootball/europe          domestic leagues of 50 countries, football.txt (CC0)
- openfootball/football.json   top leagues, JSON (CC0)
- openfootball/champions-league  UEFA competitions to 2025/26 (CC0)
- xgabora/Club-Football-Match-Data  Matches.csv: 25 leagues with Elo and odds (MIT)

Each is saved under paths.SOURCES, replacing the previous copy; sources.json records when.
"""
from __future__ import annotations

import io
import json
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone

import paths

UA = {"User-Agent": "football-predictor/1.0 (+https://github.com/langsimon77/football-predictor)"}
REPOS = {"europe": "openfootball/europe", "football.json": "openfootball/football.json", "champions-league": "openfootball/champions-league"}
MATCHES = "https://raw.githubusercontent.com/xgabora/Club-Football-Match-Data/main/data/Matches.csv"


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def main() -> int:
    log = {}
    for name, repo in REPOS.items():
        data = get(f"https://codeload.github.com/{repo}/zip/refs/heads/master")
        dest = paths.SOURCES / name
        shutil.rmtree(dest, ignore_errors=True)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = z.namelist()[0].split("/")[0]
            for m in z.infolist():
                if m.is_dir() or not m.filename.startswith(root + "/"):
                    continue
                target = dest / m.filename[len(root) + 1:]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(m))
        log[name] = {"repo": repo, "bytes": len(data)}
    csv = paths.SOURCES / "Club-Football-Match-Data" / "data" / "Matches.csv"
    csv.parent.mkdir(parents=True, exist_ok=True)
    body = get(MATCHES)
    csv.write_bytes(body)
    log["Club-Football-Match-Data"] = {"url": MATCHES, "bytes": len(body)}
    log["fetched_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    (paths.SOURCES / "sources.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(json.dumps(log, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
