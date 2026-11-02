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
