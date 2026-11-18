"""A spent ChatGPT usage window that the account's Codex credits extend reads as over pace
while the balance stays above TAUCETI_CODEX_CREDIT_FLOOR."""

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ.pop("TAUCETI_CONF", None)

import tauceti_worker as tc  # noqa: E402
from tauceti_worker.loop import _ignore_quota_verdict  # noqa: E402
from tauceti_worker.quota import _unavail_reason  # noqa: E402

WEEK = 604800
q = tc.Quota.__new__(tc.Quota)


def payload(used=100, *, allowed=True, limit_reached=False, has_credits=True, unlimited=False,
            overage=False, balance="59004.9747765000"):
    # The shape the endpoint returned for this account once its weekly window was spent.
    return {
        "plan_type": "pro",
        "rate_limit": {
            "allowed": allowed,
            "limit_reached": limit_reached,
            "primary_window": {"used_percent": used, "limit_window_seconds": WEEK, "reset_after_seconds": 167438},
            "secondary_window": None,
        },
        "credits": {"has_credits": has_credits, "unlimited": unlimited, "overage_limit_reached": overage,
                    "balance": balance},
    }


def status(p):
    prov = q._codex_from_payload(p)
    return [w.status for w in prov.windows], prov.available, _ignore_quota_verdict(None, prov)


def with_floor(value):
    if value is None:
        os.environ.pop("TAUCETI_CODEX_CREDIT_FLOOR", None)
    else:
        os.environ["TAUCETI_CODEX_CREDIT_FLOOR"] = value


def test_credits_above_the_floor():
    with_floor("20000")
    # Over pace, not available: an ignore_quota worker runs, a paced worker still waits.
    assert status(payload()) == (["over-pace"], False, "over-pace")
    assert _unavail_reason(q._codex_from_payload(payload()))[0] is True
    assert status(payload(unlimited=True, has_credits=False, balance=None))[2] == "over-pace"
    # The plan's own limit reached, as the endpoint reports it once the included usage is spent:
    # the credits still cover the request.
    reached = payload(allowed=False, limit_reached=True)
    assert status(reached) == (["over-pace"], False, "over-pace")


def test_spent_window_stays_exhausted():
    with_floor("20000")
    for p in (
        payload(balance="20000"),
        payload(balance="19999.5"),
        payload(has_credits=False),
        payload(overage=True),
        payload(allowed=False, limit_reached=True, balance="19999.5"),
        payload(balance="not a number"),
        {k: v for k, v in payload().items() if k != "credits"},
    ):
        assert status(p) == (["exhausted"], False, "wait"), p
    missing = payload()
    del missing["credits"]["overage_limit_reached"]
    assert status(missing)[0] == ["exhausted"]


def test_without_a_floor():
    for value in (None, "", "-1", "inf", "lots"):
        with_floor(value)
        assert status(payload()) == (["exhausted"], False, "wait"), value


def test_windows_with_headroom_are_untouched():
    with_floor("20000")
    assert status(payload(used=10))[0] == ["under-pace"]


if __name__ == "__main__":
    try:
        for name, test in sorted(globals().items()):
            if name.startswith("test_"):
                test()
                print(f"ok {name}")
    finally:
        with_floor(None)
