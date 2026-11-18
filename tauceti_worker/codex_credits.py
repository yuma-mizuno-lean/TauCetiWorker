"""Codex credits extend a spent ChatGPT usage window (ported from AutoMathWorker's automath_credits).

When a ChatGPT plan's usage window reaches 100%, the account can keep running Codex on its credits:
the usage endpoint then still reports `rate_limit.allowed`, with `credits.has_credits` and a balance.
Upstream's pacer reads only the windows, so a window at 100% is `exhausted` and the worker waits for
the reset. With TAUCETI_CODEX_CREDIT_FLOOR set, a spent window reads as over pace while the balance
stays above the floor: real quota remains, so a worker with `ignore_quota` runs and a paced worker
still waits. At or below the floor, or once the endpoint reports the limit or the overage limit
reached, the window stays exhausted.
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
    rate = payload.get("rate_limit")
    credits = payload.get("credits")
    if limit is None or not isinstance(rate, dict) or not isinstance(credits, dict):
        return False
    if rate.get("allowed") is not True or rate.get("limit_reached") is not False:
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
