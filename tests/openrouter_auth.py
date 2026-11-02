#!/usr/bin/env python3
"""OpenRouter login is resolved before worker HOME isolation, without exposing secrets."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tauceti_worker.openrouter_auth import ensure_openrouter_key, ensure_pi_model

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


model = "minimax/minimax-m3.1-flash"
ok = subprocess.CompletedProcess([], 0, f"provider model\nopenrouter {model} 1M\n", "")
fuzzy = subprocess.CompletedProcess([], 0, f"provider model\nopenrouter {model}:free 1M\n", "")
updated = subprocess.CompletedProcess([], 0, "Model catalogs refreshed", "")
with patch("subprocess.run", side_effect=[fuzzy, updated, ok]) as run:
    ensure_pi_model(model, {"HOME": "/isolated"})
    assert run.call_count == 3
    assert run.call_args_list[1].args[0] == ["pi", "update", "--models"]
with patch("subprocess.run", side_effect=[fuzzy, updated, fuzzy]):
    try:
        ensure_pi_model(model, {})
    except RuntimeError as error:
        assert "exact" in str(error)
    else:
        raise AssertionError("fuzzy match must not be accepted")
with patch("subprocess.run", return_value=ok) as run:
    ensure_pi_model(model, {})
    assert run.call_count == 1
print("Pi exact model catalog: OK")
