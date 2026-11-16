"""The download helper: when a saved copy is reused and when it is fetched again."""

import os
import time

from fp.ingest import http


def _setup(tmp_path, monkeypatch, bodies):
    calls = []

    def fake_get(url, headers, attempts=http.RETRY_ATTEMPTS):
        calls.append(url)
        return bodies[min(len(calls), len(bodies)) - 1]

    monkeypatch.setattr(http, "RAW_DIR", tmp_path)
    monkeypatch.setattr(http, "_get_with_retries", fake_get)
    return calls


def test_todays_copy_is_reused_by_default(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, [b"first", b"second"])
    http.fetch("https://example.org/a", "src", "a.json")
    path = http.fetch("https://example.org/a", "src", "a.json")
    assert len(calls) == 1
    assert path.read_bytes() == b"first"


def test_todays_copy_older_than_max_age_is_fetched_again(tmp_path, monkeypatch):
    # Review of Nov 2026: the basketball job runs four times a day, but runs 2 to 4
    # reused the first run's pages, so results reached the ledger up to a day late.
    calls = _setup(tmp_path, monkeypatch, [b"first", b"second"])
    path = http.fetch("https://example.org/a", "src", "a.json", max_age_hours=3)
    old = time.time() - 4 * 3600
    os.utime(path, (old, old))
    again = http.fetch("https://example.org/a", "src", "a.json", max_age_hours=3)
    assert len(calls) == 2
    assert again == path
    assert again.read_bytes() == b"second"


def test_fresh_copy_within_max_age_is_reused(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, [b"first", b"second"])
    http.fetch("https://example.org/a", "src", "a.json", max_age_hours=3)
    path = http.fetch("https://example.org/a", "src", "a.json", max_age_hours=3)
    assert len(calls) == 1
    assert path.read_bytes() == b"first"


def test_failed_refresh_keeps_the_copy_we_have(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, [b"first"])
    path = http.fetch("https://example.org/a", "src", "a.json", max_age_hours=3)
    old = time.time() - 4 * 3600
    os.utime(path, (old, old))

    def broken(url, headers, attempts=http.RETRY_ATTEMPTS):
        raise http.requests.ConnectionError("down")

    monkeypatch.setattr(http, "_get_with_retries", broken)
    again = http.fetch("https://example.org/a", "src", "a.json", max_age_hours=3)
    assert again.read_bytes() == b"first"


def test_offline_never_downloads(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, [b"first", b"second"])
    path = http.fetch("https://example.org/a", "src", "a.json", max_age_hours=3)
    old = time.time() - 4 * 3600
    os.utime(path, (old, old))
    http.fetch("https://example.org/a", "src", "a.json", refresh=False, max_age_hours=3)
    assert len(calls) == 1
