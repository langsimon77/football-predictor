"""Secrets and settings.

Keys come from environment variables (GitHub Actions secrets) or, locally, from
the git-ignored .env file in the project root. Never print or log a key.
"""

from __future__ import annotations

import os
from functools import cache

from fp import ROOT

ENV_FILE = ROOT / ".env"


class MissingSecretError(RuntimeError):
    pass


@cache
def _dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            values[name.strip()] = value.strip().strip("'\"")
    return values


def secret(name: str) -> str:
    """Return a secret by name. Environment variables win over .env."""
    value = os.environ.get(name) or _dotenv().get(name)
    if not value:
        raise MissingSecretError(f"{name} is not set in the environment or .env")
    return value
