#!/usr/bin/env python3
"""Open Math OS is an opt-in host agent for authoring and repair."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tauceti_worker import agents, cli, openmathos
from tauceti_worker.config import Die
from tauceti_worker.loop import resolve_work_model
from tauceti_worker.worker_manager import WorkersError, WorkerSpec

MODEL = "claude-openmathos-test"


class OpenMathOSTest(unittest.TestCase):
    def test_cli_defaults_to_source_changes(self):
        with patch.object(cli, "cmd_work", return_value=0) as run:
            self.assertEqual(cli.main(["work", "--agent", "openmathos", "--author-model", MODEL]), 0)
        self.assertEqual(run.call_args.kwargs["only"], list(openmathos.TASKS))

    def test_cli_rejects_reviews(self):
        for flags in (["--only", "review"], ["--only", "fix,review"]):
            with self.subTest(flags=flags), patch.object(cli, "cmd_work") as run:
                with self.assertRaisesRegex(Die, "only supports"):
                    cli.main(["work", "--agent", "openmathos", "--author-model", MODEL, *flags])
                run.assert_not_called()

    def test_worker_config_rejects_reviews_and_bubble(self):
        spec = {"id": "openmathos", "agent": "openmathos", "author_model": MODEL}
        for flags in ({"only": ["review"]}, {"sandbox": "bubble"}):
            with self.subTest(flags=flags), self.assertRaisesRegex(WorkersError, "Open Math OS"):
                WorkerSpec.from_dict(spec | flags, 0)
        self.assertEqual(WorkerSpec.from_dict(spec | {"only": ["fix"]}, 0).author_model, MODEL)

    def test_host_launch_pins_gateway_and_model(self):
        credentials = {
            "OPENMATHOS_API_KEY": "test-gateway-key",
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "CLAUDE_CODE_OAUTH_TOKEN": "test-subscription-token",
        }
        with patch.dict(os.environ, credentials):
            profile = agents.resolve_authoring_profile("openmathos", cli_model=MODEL)
            argv, env, stdin = agents.host_agent_launch("test prompt", profile)
        self.assertEqual(argv[argv.index("--model") + 1], MODEL)
        self.assertEqual(env["ANTHROPIC_BASE_URL"], openmathos.BASE_URL)
        self.assertEqual(env["ANTHROPIC_AUTH_TOKEN"], credentials["OPENMATHOS_API_KEY"])
        self.assertEqual(env["ANTHROPIC_DEFAULT_SONNET_MODEL"], MODEL)
        self.assertTrue(set(credentials).isdisjoint(env))
        self.assertIsNone(stdin)

    def test_explicit_model_and_unpaced_resolution(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(Die, "--author-model"):
                agents.resolve_authoring_profile("openmathos")
        self.assertEqual(resolve_work_model(None, "openmathos", dry=False, ignore_quota=False), "openmathos")

    def test_gateway_requires_exact_model(self):
        with patch.object(openmathos, "available_models", return_value=[MODEL]):
            with self.assertRaisesRegex(RuntimeError, "does not list exact model"):
                openmathos.ensure_model(MODEL + "-other")
            openmathos.ensure_model(MODEL)


if __name__ == "__main__":
    unittest.main()
