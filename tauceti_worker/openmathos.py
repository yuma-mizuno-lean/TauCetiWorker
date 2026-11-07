"""Open Math OS: Claude Code driven against the Open Math OS gateway, as its own agent.

Mei fork addition. `--agent openmathos` runs the same `claude` CLI as `--agent claude`, but every
request goes to the Open Math OS Claude-compatible endpoint with the operator's Open Math OS key.
It is a separate agent on purpose: `--agent claude` keeps using the operator's Anthropic
subscription or API billing, and nothing here changes it.

The model has no default. The gateway's routing ids are opaque and may change, so the exact id is
configured once, as the worker's `author_model` (`--author-model`), and used for both authoring and
review. Reviews go through the review engine's `openmathos` reviewer (`--openmathos-model`), which
the project's `[tools.review]` pin must provide. Like the OpenRouter and Kiro agents it is unpaced
(Open Math OS publishes no quota telemetry the worker can read) and runs on the host only.

The key follows the OpenRouter agents: resolved before HOME isolation and handed on in the
environment (OPENMATHOS_API_KEY), so loop children and the review engine see it after isolation.

Everything provider-specific lives in this module so that merging upstream touches few lines.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

PROVIDER = "openmathos"
BASE_URL = "https://os.openmathmodel.org/claude"
KEY_ENV = "OPENMATHOS_API_KEY"
KEY_FILE_ENV = "OPENMATHOS_API_KEY_FILE"
DEFAULT_KEY_FILE = "~/.config/tauceti/openmathos.key"

# Claude Code picks these for its own side requests (titles, summaries, subagents). Pin them all to
# the authoring model so that no request names a model the gateway does not serve.
_MODEL_VARIABLES = (
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_FABLE_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
)

_verified: set[str] = set()


def is_openmathos(provider: str | None) -> bool:
    return provider == PROVIDER


def transcript_provider(provider: str) -> str:
    """The CLI whose stream-json events this provider prints."""
    return "claude" if provider == PROVIDER else provider


def ensure_key() -> None:
    """Keep an explicit OPENMATHOS_API_KEY; otherwise read the key file into it.

    Called before HOME isolation, so `~` still means the operator's home. A missing key does not
    heal by waiting, so it stops the worker rather than backing off."""
    from .config import Die

    if (os.environ.get(KEY_ENV) or "").strip():
        return
    path = Path(os.environ.get(KEY_FILE_ENV) or DEFAULT_KEY_FILE).expanduser()
    try:
        key = path.read_text().strip()
    except OSError:
        raise Die(f"Open Math OS key unavailable; write it to {path} (mode 0600) or set {KEY_ENV}") from None
    if not key or "\n" in key or "\r" in key:
        raise Die(f"Open Math OS key in {path} must be a single line")
    os.environ[KEY_ENV] = key


def _key(env) -> str:
    key = (env.get(KEY_ENV) or "").strip()
    if not key:
        from .config import Die

        raise Die(f"{KEY_ENV} is not set; the worker resolves it at start-up")
    return key


def process_env(env: dict, model: str) -> dict:
    """The claude process environment for one Open Math OS authoring round."""
    env = dict(env)
    key = _key(env)
    env.pop("ANTHROPIC_API_KEY", None)  # an Anthropic key must never reach another endpoint
    env.pop("TAUCETI_CLAUDE_BILLING", None)
    env.pop(KEY_ENV, None)  # the agent gets the key only as the gateway credential below
    env["ANTHROPIC_BASE_URL"] = BASE_URL
    env["ANTHROPIC_AUTH_TOKEN"] = key
    for name in _MODEL_VARIABLES:
        env[name] = model
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    return env


def available_models(timeout: float = 20) -> list[str]:
    request = urllib.request.Request(
        BASE_URL + "/v1/models",
        headers={
            "Authorization": "Bearer " + _key(os.environ),
            "Accept": "application/json",
            "User-Agent": "tauceti-worker",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.load(response)
    rows = body.get("data", body) if isinstance(body, dict) else body
    return [row["id"] for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)]


def ensure_model(model: str) -> None:
    """Refuse to launch unless the gateway lists this exact model id (no silent substitution)."""
    if model in _verified:
        return
    try:
        models = available_models()
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Open Math OS model list failed: HTTP {error.code}") from None
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Open Math OS model list unavailable: {error}") from None
    if model not in models:
        raise RuntimeError(
            f"Open Math OS does not list exact model {model!r}; available: {', '.join(sorted(models)) or 'none'}"
        )
    _verified.add(model)


def review_model(reviewers: str) -> str | None:
    """The exact model for the review engine's openmathos reviewer: the worker's own configured
    model, resolved like any authoring profile (as _kiro_review_model does for Kiro)."""
    if PROVIDER not in [r.strip() for r in reviewers.split(",")]:
        return None
    from .agents import resolve_authoring_profile

    return resolve_authoring_profile(PROVIDER).model
