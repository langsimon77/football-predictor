"""Polite HTTP downloads: one place for the scraping rules in spec S2.

Rules enforced here:
- A clear User-Agent names the project.
- At most 1 request every 3 seconds per domain.
- Every response is saved under data/raw/<source>/<YYYY-MM-DD>/. A saved file is never
  edited by hand; today's copy is replaced only by a newer download of the same address.
- A file that is already cached is read from disk instead of downloaded again. A caller
  that runs several times a day may ask for today's copy to be replaced once it is older
  than a set number of hours (max_age_hours).
- Timeouts and dropped connections are retried, because connections can be slow.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

from fp import ROOT

USER_AGENT = (
    "football-predictor/0.1 (+https://github.com/langsimon77/football-predictor; "
    "non-commercial research; max 1 request per 3 s) python-requests"
)
MIN_SECONDS_BETWEEN_REQUESTS = 3.0
# APIs with published limits of 10 calls a minute get a slower pace.
DOMAIN_INTERVALS = {"api.football-data.org": 6.5, "v3.football.api-sports.io": 6.5}
RETRY_ATTEMPTS = 3
RAW_DIR = ROOT / "data" / "raw"

# Time of the last request to each domain, for the rate limit.
_last_request_at: dict[str, float] = {}


def _wait_for_domain(domain: str) -> None:
    last = _last_request_at.get(domain)
    if last is not None:
        interval = DOMAIN_INTERVALS.get(domain, MIN_SECONDS_BETWEEN_REQUESTS)
        wait = interval - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_request_at[domain] = time.monotonic()


def today_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def cached_copies(source: str, filename: str) -> list[Path]:
    """All dated copies of one file, oldest first."""
    return sorted((RAW_DIR / source).glob(f"*/{filename}"))


def fetch(
    url: str,
    source: str,
    filename: str,
    *,
    refresh: bool = True,
    headers: dict[str, str] | None = None,
    max_age_hours: float | None = None,
) -> Path:
    """Download url into data/raw/<source>/<today>/<filename> and return the path.

    refresh=True: download unless today's copy already exists.
    refresh=False: reuse the newest copy from any date. Use this for files that
    no longer change, such as completed seasons.
    max_age_hours (with refresh=True): also download when today's copy is older than
    this. For jobs that run several times a day: without it, every run after the first
    reads the first run's copy. If that download fails, the copy we have is kept.
    """
    todays = RAW_DIR / source / today_utc() / filename
    if todays.exists():
        age_hours = (time.time() - todays.stat().st_mtime) / 3600
        if not refresh or max_age_hours is None or age_hours <= max_age_hours:
            return todays
        try:
            todays.write_bytes(_get_with_retries(url, headers or {}))
        except requests.RequestException:
            pass
        return todays
    if not refresh:
        copies = cached_copies(source, filename)
        if copies:
            return copies[-1]

    content = _get_with_retries(url, headers or {})
    todays.parent.mkdir(parents=True, exist_ok=True)
    todays.write_bytes(content)
    return todays


def _get_with_retries(
    url: str, headers: dict[str, str], attempts: int = RETRY_ATTEMPTS
) -> bytes:
    """GET with retries on timeouts and dropped connections. Waits 10 s, then 20 s."""
    for attempt in range(1, attempts + 1):
        _wait_for_domain(urlparse(url).netloc)
        try:
            response = requests.get(
                url, headers={"User-Agent": USER_AGENT, **headers}, timeout=60
            )
            if response.status_code == 429 and attempt < attempts:
                # Too many requests: wait as the server asks (at most 2 minutes), then retry.
                retry_after = response.headers.get("Retry-After", "")
                time.sleep(min(int(retry_after) if retry_after.isdigit() else 30 * attempt, 120))
                continue
            response.raise_for_status()
            return response.content
        except (requests.Timeout, requests.ConnectionError):
            if attempt == attempts:
                raise
            time.sleep(10 * attempt)
    raise AssertionError("unreachable")
