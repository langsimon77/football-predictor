"""Write ledger/basketball/page_feed.json: the Model Lab's basketball cards for the leagues the
GitHub run covers (EuroLeague, NBL, ACB, LBA, ABA), from ledger/basketball/upcoming.parquet.

Run by .github/workflows/basketball.yml after each daily step. A scheduled Claude task copies
this file into the Model Lab page's database (document live/basketball), so the page shows the
latest run without a republish (Lang, 14 Nov 2026: "make sure the page is refreshed").

    uv run python scripts/basketball_feed.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from build_model_lab import BASKETBALL_UPCOMING, basketball_block  # noqa: E402

from fp import ROOT  # noqa: E402

FEED = ROOT / "ledger" / "basketball" / "page_feed.json"


def main() -> int:
    block = basketball_block(BASKETBALL_UPCOMING)
    if block is None:
        print("no upcoming basketball file; feed not written")
        return 0
    feed = {"as_of": block["as_of"], "rows": block["rows"], "test": block["test"],
            "source": "football-predictor basketball/live.py (Wikipedia)"}
    FEED.write_text(json.dumps(feed, ensure_ascii=False, separators=(",", ":")) + "\n",
                    encoding="utf-8")
    leagues = sorted({r["lg"] for r in feed["rows"]})
    print(f"wrote {FEED.relative_to(ROOT)}: {len(feed['rows'])} games ({', '.join(leagues)}), "
          f"as of {feed['as_of']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
