"""Fail if any em dash (U+2014) or en dash (U+2013) appears in docs, code, or app text.

Spec S0 bans both characters. docs/SPEC.md is exempt because it is Lang's
original prompt, stored verbatim.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANNED = {chr(0x2014): "em dash", chr(0x2013): "en dash"}
SUFFIXES = {".md", ".py", ".toml", ".yml", ".yaml", ".csv", ".html", ".json", ".txt"}
SKIP_DIRS = {".venv", ".git", "data/raw", "data/interim", ".pytest_cache", ".ruff_cache"}
EXEMPT = {ROOT / "docs" / "SPEC.md"}


def files() -> list[Path]:
    out = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        if any(rel == d or rel.startswith(d + "/") for d in SKIP_DIRS):
            continue
        if path.is_file() and path.suffix in SUFFIXES and path not in EXEMPT:
            out.append(path)
    return out


def main() -> int:
    hits = []
    for path in files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for char, label in BANNED.items():
                if char in line:
                    hits.append(f"{path.relative_to(ROOT)}:{number}: {label}")
    for hit in hits:
        print(hit)
    print(f"dash check: {len(hits)} problem(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
