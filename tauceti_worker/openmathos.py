"""Open Math OS: Claude Code driven against the Open Math OS gateway, as its own agent.

Mei fork addition. `--agent openmathos` runs the same `claude` CLI as `--agent claude`, but every
request goes to the Open Math OS Claude-compatible endpoint with the operator's Open Math OS key.
It is a separate agent on purpose: `--agent claude` keeps using the operator's Anthropic
subscription or API billing, and nothing here changes it. Like the OpenRouter and Kiro agents it is
unpaced (Open Math OS publishes no quota telemetry the worker can read), runs on the host only, and
never reviews: the review engine would record its verdicts as Claude reviews.

Everything provider-specific lives in this module so that merging upstream touches few lines.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

PROVIDER = "openmathos"
NAME = "Open Math OS"
DEFAULT_MODEL = "claude-openmathos-k3"
DEFAULT_EFFORT = "high"
DEFAULT_BASE_URL = "https://os.openmathmodel.org/claude"
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

_verified: set[tuple[str, str]] = set()


def is_openmathos(provider: str | None) -> bool:
    return provider == PROVIDER


def transcript_provider(provider: str) -> str:
    """The CLI whose stream-json events this provider prints."""
    return "claude" if provider == PROVIDER else provider


def base_url(env: dict | None = None) -> str:
    env = os.environ if env is None else env
    return (env.get("OPENMATHOS_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def key_file(env: dict | None = None) -> Path:
    env = os.environ if env is None else env
    return Path(env.get("OPENMATHOS_API_KEY_FILE") or DEFAULT_KEY_FILE).expanduser()


def api_key(env: dict | None = None) -> str:
    """An explicit OPENMATHOS_API_KEY wins; otherwise read the 0600 key file.

    A missing key does not heal by waiting, so it stops the worker (Die) rather than backing off."""
    from .config import Die

    env = os.environ if env is None else env
    key = (env.get("OPENMATHOS_API_KEY") or "").strip()
    if not key:
        path = key_file(env)
        try:
            key = path.read_text().strip()
        except OSError:
            raise Die(
                f"Open Math OS key unavailable; write it to {path} (mode 0600) or set OPENMATHOS_API_KEY"
            ) from None
    if not key or "\n" in key or "\r" in key:
        raise Die("Open Math OS key must be a single line")
    return key


def authoring_only(only: list[str], allowed: list[str]) -> list[str]:
    """Restrict an Open Math OS worker to authoring phases; review is never delegated to it."""
    if "review" in only:
        raise RuntimeError("--agent openmathos cannot review; drop review from --only")
    return list(only) if only else [task for task in allowed if task != "review"]


def process_env(env: dict, model: str) -> dict:
    """The claude process environment for one Open Math OS round."""
    env = dict(env)
    env.pop("ANTHROPIC_API_KEY", None)  # an Anthropic key must never reach another endpoint
    env.pop("TAUCETI_CLAUDE_BILLING", None)
    env["ANTHROPIC_BASE_URL"] = base_url(env)
    env["ANTHROPIC_AUTH_TOKEN"] = api_key(env)
    for name in _MODEL_VARIABLES:
        env[name] = model
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    env.pop("OPENMATHOS_API_KEY", None)
    return env


def available_models(env: dict | None = None, timeout: float = 20) -> list[str]:
    request = urllib.request.Request(
        base_url(env) + "/v1/models",
        headers={
            "Authorization": "Bearer " + api_key(env),
            "Accept": "application/json",
            "User-Agent": "tauceti-worker",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.load(response)
    rows = body.get("data", body) if isinstance(body, dict) else body
    return [row["id"] for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)]


def ensure_model(model: str, env: dict | None = None) -> None:
    """Refuse to launch unless the gateway lists this exact model id (no silent substitution)."""
    marker = (base_url(env), model)
    if marker in _verified:
        return
    try:
        models = available_models(env)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Open Math OS model list failed: HTTP {error.code}") from None
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Open Math OS model list unavailable: {error}") from None
    if model not in models:
        raise RuntimeError(
            f"Open Math OS does not list exact model {model!r}; available: {', '.join(sorted(models)) or 'none'}"
        )
    _verified.add(marker)
