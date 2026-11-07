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
from tauceti_worker.constants import AGENTS, ALLOWED_TASKS

assert "openmathos" in AGENTS

with tempfile.TemporaryDirectory() as tmp:
    keyfile = Path(tmp) / "openmathos.key"
    keyfile.write_text("omos-secret\n")
    base = {"PATH": "/usr/bin", "OPENMATHOS_API_KEY_FILE": str(keyfile), "ANTHROPIC_API_KEY": "sk-ant-real"}

    # The Open Math OS profile is its own exact pin; Claude's default is untouched.
    with patch.dict(os.environ, base, clear=True):
        profile = resolve_authoring_profile("openmathos")
        assert (profile.model, profile.effort) == (openmathos.DEFAULT_MODEL, openmathos.DEFAULT_EFFORT)
        claude = resolve_authoring_profile("claude")
        assert not claude.model.startswith("claude-openmathos")

        argv, env = host_agent_argv("hello", profile)
        assert argv[0] == "claude" and "-p" in argv and "--dangerously-skip-permissions" in argv
        assert argv[argv.index("--model") + 1] == openmathos.DEFAULT_MODEL
        assert env["ANTHROPIC_BASE_URL"] == openmathos.DEFAULT_BASE_URL
        assert env["ANTHROPIC_AUTH_TOKEN"] == "omos-secret"
        assert "ANTHROPIC_API_KEY" not in env, "an Anthropic key must never reach the gateway"
        for name in ("ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_SMALL_FAST_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL"):
            assert env[name] == openmathos.DEFAULT_MODEL
        assert env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"

        # --agent claude gets no gateway variables.
        _, claude_env = host_agent_argv("hello", claude)
        assert "ANTHROPIC_BASE_URL" not in claude_env and "ANTHROPIC_AUTH_TOKEN" not in claude_env

    # Long prompts go through stdin like Claude; transcripts parse as Claude stream-json.
    assert prompt_on_stdin("x" * (65 * 1024), "openmathos")
    assert AgentTranscriptRenderer(openmathos.transcript_provider("openmathos")).provider == "claude"
    # Bubble never receives the Claude subscription credential for this agent.
    assert "--no-claude-credentials" in agent_cred_flags("openmathos")

    # An explicit key wins over the file; a missing key stops the worker without leaking anything.
    with patch.dict(os.environ, {**base, "OPENMATHOS_API_KEY": "from-env"}, clear=True):
        assert openmathos.api_key() == "from-env"
    with patch.dict(os.environ, {"OPENMATHOS_API_KEY_FILE": str(Path(tmp) / "absent")}, clear=True):
        try:
            openmathos.api_key()
        except Die as error:
            assert "absent" in str(error)
        else:
            raise AssertionError("missing key must stop the worker")

    # Review is never delegated to Open Math OS.
    assert "review" not in openmathos.authoring_only([], ALLOWED_TASKS)
    assert openmathos.authoring_only(["fix"], ALLOWED_TASKS) == ["fix"]
    try:
        openmathos.authoring_only(["fix", "review"], ALLOWED_TASKS)
    except RuntimeError:
        pass
    else:
        raise AssertionError("review must be refused")

    # The launch preflight accepts only an exact listed model id and sends the key as a bearer token.
    def listing(*ids):
        def urlopen(request, timeout):
            assert request.full_url == openmathos.DEFAULT_BASE_URL + "/v1/models"
            assert request.get_header("Authorization") == "Bearer omos-secret"
            return io.BytesIO(json.dumps({"data": [{"id": i} for i in ids]}).encode())

        return urlopen

    with patch.dict(os.environ, base, clear=True):
        openmathos._verified.clear()
        with patch("urllib.request.urlopen", listing("claude-openmathos-k3-preview")):
            try:
                openmathos.ensure_model("claude-openmathos-k3")
            except RuntimeError as error:
                assert "exact" in str(error) and "omos-secret" not in str(error)
            else:
                raise AssertionError("a near match must not be accepted")
        with patch("urllib.request.urlopen", listing("claude-openmathos-k3")) as urlopen:
            openmathos.ensure_model("claude-openmathos-k3")
            openmathos.ensure_model("claude-openmathos-k3")
        with patch("urllib.request.urlopen", side_effect=AssertionError("cached")):
            openmathos.ensure_model("claude-openmathos-k3")

print("Open Math OS agent: OK")
