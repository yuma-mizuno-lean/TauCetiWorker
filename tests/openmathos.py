#!/usr/bin/env python3
"""The Open Math OS agent runs Claude Code against its gateway and leaves `--agent claude` alone."""

import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tauceti_worker import openmathos
from tauceti_worker.agents import (
    AgentTranscriptRenderer,
    agent_cred_flags,
    host_agent_argv,
    prompt_on_stdin,
    resolve_authoring_profile,
)
from tauceti_worker.config import Die
from tauceti_worker.constants import AGENTS
from tauceti_worker.work_units import _host_agent_binary

MODEL = "claude-openmathos-example"
assert "openmathos" in AGENTS


def dies(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Die as error:
        return str(error)
    raise AssertionError(f"{fn.__name__} must stop the worker")


# No model is written in the code: the worker's author_model is required.
with patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
    assert "must not be empty" in dies(resolve_authoring_profile, "openmathos")
    profile = resolve_authoring_profile("openmathos", cli_model=MODEL)
    assert (profile.model, profile.effort) == (MODEL, "high")
    assert not resolve_authoring_profile("claude").model.startswith("claude-openmathos")

with tempfile.TemporaryDirectory() as tmp:
    keyfile = Path(tmp) / "openmathos.key"
    keyfile.write_text("omos-secret\n")

    # ensure_key reads the file once, before HOME isolation, into the environment it hands on.
    with patch.dict(os.environ, {"OPENMATHOS_API_KEY_FILE": str(keyfile)}, clear=True):
        openmathos.ensure_key()
        assert os.environ["OPENMATHOS_API_KEY"] == "omos-secret"
        os.environ["HOME"] = str(Path(tmp) / "isolated")  # isolation must not lose the key
        os.environ.pop("OPENMATHOS_API_KEY_FILE")
        openmathos.ensure_key()
        assert os.environ["OPENMATHOS_API_KEY"] == "omos-secret"
    with patch.dict(
        os.environ, {"OPENMATHOS_API_KEY": "from-env", "OPENMATHOS_API_KEY_FILE": str(keyfile)}, clear=True
    ):
        openmathos.ensure_key()
        assert os.environ["OPENMATHOS_API_KEY"] == "from-env", "an explicit key wins"
    with patch.dict(os.environ, {"OPENMATHOS_API_KEY_FILE": str(Path(tmp) / "absent")}, clear=True):
        assert "absent" in dies(openmathos.ensure_key)

base = {"PATH": "/usr/bin", "OPENMATHOS_API_KEY": "omos-secret", "ANTHROPIC_API_KEY": "sk-ant-real"}
with patch.dict(os.environ, base, clear=True):
    profile = resolve_authoring_profile("openmathos", cli_model=MODEL)
    argv, env = host_agent_argv("hello", profile)
    assert argv[0] == "claude" and "-p" in argv and "--dangerously-skip-permissions" in argv
    assert argv[argv.index("--model") + 1] == MODEL
    assert env["ANTHROPIC_BASE_URL"] == openmathos.BASE_URL
    assert env["ANTHROPIC_AUTH_TOKEN"] == "omos-secret"
    assert "ANTHROPIC_API_KEY" not in env, "an Anthropic key must never reach the gateway"
    assert "OPENMATHOS_API_KEY" not in env, "the agent gets the key only as the gateway credential"
    for name in ("ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_SMALL_FAST_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL"):
        assert env[name] == MODEL
    assert env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"

    # --agent claude gets no gateway variables.
    _, claude_env = host_agent_argv("hello", resolve_authoring_profile("claude"))
    assert "ANTHROPIC_BASE_URL" not in claude_env and "ANTHROPIC_AUTH_TOKEN" not in claude_env

with patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True):
    assert "OPENMATHOS_API_KEY" in dies(openmathos.process_env, {}, MODEL)

# A bare provider name resolves through the published authoring variable (preflights use it).
with patch.dict(os.environ, {"TAUCETI_AUTHORING_OPENMATHOS_MODEL": MODEL, "OPENMATHOS_API_KEY": "k"}, clear=True):
    assert resolve_authoring_profile("openmathos").model == MODEL
    # Long prompts go through stdin like Claude; transcripts parse as Claude stream-json.
    assert prompt_on_stdin("x" * (65 * 1024), "openmathos")
    assert _host_agent_binary("fix", "openmathos") == "claude"
assert AgentTranscriptRenderer(openmathos.transcript_provider("openmathos")).provider == "claude"
# Bubble never receives the Claude subscription credential for this agent.
assert "--no-claude-credentials" in agent_cred_flags("openmathos")

# Reviews: the engine's openmathos reviewer gets the worker's own model, through `claude`.
with patch.dict(os.environ, {"TAUCETI_AUTHORING_OPENMATHOS_MODEL": MODEL}, clear=True):
    assert openmathos.review_model("openmathos") == MODEL
    assert openmathos.review_model("claude") is None
assert _host_agent_binary("review", "openmathos") == "claude"


# The launch preflight accepts only an exact listed model id and sends the key as a bearer token.
def listing(*ids):
    def urlopen(request, timeout):
        assert request.full_url == openmathos.BASE_URL + "/v1/models"
        assert request.get_header("Authorization") == "Bearer omos-secret"
        return io.BytesIO(json.dumps({"data": [{"id": i} for i in ids]}).encode())

    return urlopen


with patch.dict(os.environ, base, clear=True):
    openmathos._verified.clear()
    with patch("urllib.request.urlopen", listing(MODEL + "-preview")):
        try:
            openmathos.ensure_model(MODEL)
        except RuntimeError as error:
            assert "exact" in str(error) and "omos-secret" not in str(error)
        else:
            raise AssertionError("a near match must not be accepted")
    with patch("urllib.request.urlopen", listing(MODEL)):
        openmathos.ensure_model(MODEL)
    with patch("urllib.request.urlopen", side_effect=AssertionError("cached")):
        openmathos.ensure_model(MODEL)

print("Open Math OS agent: OK")
