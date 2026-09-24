"""Polite HTTP downloads: one place for the scraping rules in spec S2.

Rules enforced here:
- A clear User-Agent names the project.
- At most 1 request every 3 seconds per domain.
- Every response is saved under data/raw/<source>/<YYYY-MM-DD>/ and never edited.
- A file that is already cached is read from disk instead of downloaded again.
- Timeouts and dropped connections are retried, because connections can be slow.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

from fp import ROOT

USER_AGENT = "football-predictor/0.1 (non-commercial research project; max 1 request per 3 s)"
MIN_SECONDS_BETWEEN_REQUESTS = 3.0
RETRY_ATTEMPTS = 3
RAW_DIR = ROOT / "data" / "raw"

# Time of the last request to each domain, for the rate limit.
_last_request_at: dict[str, float] = {}


def _wait_for_domain(domain: str) -> None:
    last = _last_request_at.get(domain)
    if last is not None:
        wait = MIN_SECONDS_BETWEEN_REQUESTS - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_request_at[domain] = time.monotonic()


def today_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def cached_copies(source: str, filename: str) -> list[Path]:
    """All dated copies of one file, oldest first."""
    return sorted((RAW_DIR / source).glob(f"*/{filename}"))


def fetch(url: str, source: str, filename: str, *, refresh: bool = True) -> Path:
    """Download url into data/raw/<source>/<today>/<filename> and return the path.

    refresh=True: download unless today's copy already exists.
    refresh=False: reuse the newest copy from any date. Use this for files that
    no longer change, such as completed seasons.
    """
    todays = RAW_DIR / source / today_utc() / filename
    if todays.exists():
        return todays
    if not refresh:
        copies = cached_copies(source, filename)
        if copies:
            return copies[-1]

    content = _get_with_retries(url)
    todays.parent.mkdir(parents=True, exist_ok=True)
    todays.write_bytes(content)
    return todays


def _get_with_retries(url: str, attempts: int = RETRY_ATTEMPTS) -> bytes:
    """GET with retries on timeouts and dropped connections. Waits 10 s, then 20 s."""
    for attempt in range(1, attempts + 1):
        _wait_for_domain(urlparse(url).netloc)
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
            response.raise_for_status()
            return response.content
        except (requests.Timeout, requests.ConnectionError):
            if attempt == attempts:
                raise
            time.sleep(10 * attempt)
    raise AssertionError("unreachable")
