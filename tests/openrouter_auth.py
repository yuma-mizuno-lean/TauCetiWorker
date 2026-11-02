#!/usr/bin/env python3
"""OpenRouter login is resolved before worker HOME isolation, without exposing secrets."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tauceti_worker.openrouter_auth import ensure_openrouter_key

with patch.dict(os.environ, {"OPENROUTER_API_KEY": "explicit"}, clear=True):
    with patch("subprocess.run") as run:
        ensure_openrouter_key()
        assert os.environ["OPENROUTER_API_KEY"] == "explicit"
        run.assert_not_called()

with patch.dict(os.environ, {}, clear=True):
    with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "token-value\n", "")) as run:
        ensure_openrouter_key()
        assert os.environ["OPENROUTER_API_KEY"] == "token-value"
        assert run.call_args.args[0] == ["pi", "auth", "print-bearer-token", "--provider", "openrouter"]
        assert run.call_args.kwargs["capture_output"]

with patch.dict(os.environ, {}, clear=True):
    results = [subprocess.CompletedProcess([], 1, "", ""), subprocess.CompletedProcess([], 0, "api-key", "")]
    with patch("subprocess.run", side_effect=results) as run:
        ensure_openrouter_key()
        assert os.environ["OPENROUTER_API_KEY"] == "api-key"
        assert run.call_args.args[0][2] == "print-api-key"

for result in (subprocess.CompletedProcess([], 1, "", "sensitive"), subprocess.CompletedProcess([], 0, "", "")):
    with patch.dict(os.environ, {}, clear=True), patch("subprocess.run", return_value=result):
        try:
            ensure_openrouter_key()
        except RuntimeError as error:
            assert "sensitive" not in str(error)
        else:
            raise AssertionError("missing credential must fail")
print("OpenRouter credential handoff: OK")
