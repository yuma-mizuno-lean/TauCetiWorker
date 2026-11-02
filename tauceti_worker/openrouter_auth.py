"""Resolve OpenRouter credentials from the operator's Pi login before worker isolation."""

import os
import subprocess


def ensure_openrouter_key() -> None:
    """Keep an explicit key; otherwise retrieve Pi's OpenRouter OAuth credential."""
    if os.environ.get("OPENROUTER_API_KEY", "").strip():
        return
    for kind in ("print-bearer-token", "print-api-key"):
        try:
            result = subprocess.run(
                ["pi", "auth", kind, "--provider", "openrouter"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            break
        if not result.returncode and result.stdout.strip():
            os.environ["OPENROUTER_API_KEY"] = result.stdout.strip()
            return
    raise RuntimeError("OpenRouter credentials unavailable; set OPENROUTER_API_KEY or log in with pi")


def ensure_pi_model(model: str, env: dict[str, str]) -> None:
    """Reject fuzzy model substitutions; refresh the worker-local catalog once if needed."""

    def listed() -> bool:
        result = subprocess.run(
            ["pi", "--list-models", model], env=env, capture_output=True, text=True, timeout=30, check=False
        )
        return result.returncode == 0 and any(
            len(parts := line.split()) >= 2 and parts[0] == "openrouter" and parts[1] == model
            for line in result.stdout.splitlines()
        )

    try:
        if listed():
            return
        updated = subprocess.run(
            ["pi", "update", "--models"], env=env, capture_output=True, text=True, timeout=60, check=False
        )
        if updated.returncode == 0 and listed():
            return
    except (OSError, subprocess.TimeoutExpired):
        pass
    raise RuntimeError(f"Pi catalog does not contain exact OpenRouter model {model!r}; cannot launch safely")
