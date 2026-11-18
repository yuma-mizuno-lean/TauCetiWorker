"""Codex credits extend a spent ChatGPT usage window (ported from AutoMathWorker's automath_credits).

Once a ChatGPT plan's included usage is spent, Codex keeps running on the account's credits. The
usage endpoint reports the plan's own limit (`rate_limit.limit_reached`, `allowed`), not whether the
credits still cover a request; that is `credits`. Upstream's pacer reads only the plan's windows, so
a spent window is `exhausted` and the worker waits for the reset. With TAUCETI_CODEX_CREDIT_FLOOR
set, a spent window reads as over pace while the balance stays above the floor: real quota remains,
so a worker with `ignore_quota` runs and a paced worker still waits. At or below the floor, or once
the endpoint reports the overage limit reached, the window stays exhausted.
"""

from __future__ import annotations

import math
import os

FLOOR_ENV = "TAUCETI_CODEX_CREDIT_FLOOR"


def floor() -> float | None:
    """The balance at which credit spending stops, or None (credits are not spent)."""
    raw = os.environ.get(FLOOR_ENV, "").strip()
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if math.isfinite(value) and value >= 0 else None


def spendable(payload: dict) -> bool:
    """Whether the account may keep running Codex on credits above the floor. Anything missing or
    malformed reads as no."""
    limit = floor()
    credits = payload.get("credits")
    if limit is None or not isinstance(credits, dict):
        return False
    if credits.get("overage_limit_reached") is not False:
        return False
    if credits.get("unlimited") is True:
        return True
    if credits.get("has_credits") is not True:
        return False
    try:
        balance = float(credits.get("balance"))
    except (TypeError, ValueError):
        return False
    return math.isfinite(balance) and balance > limit
