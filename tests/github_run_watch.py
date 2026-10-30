"""A failing read-only watch must preserve its exit status without retaining a write."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

source = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
sys.path.insert(0, str(source))
from tauceti_worker import github_outbox as outbox
from tauceti_worker import github_transport as tr

commands = [
    ["run", "watch", "123"],
    ["run", "watch", "123", "--repo", "org/repo", "--exit-status", "--interval", "30"],
]
for args in commands:
    for exit_status in (0, 1):
        for recovery in ("0", "1"):
            with (
                tempfile.TemporaryDirectory() as root,
                patch.dict(
                    os.environ,
                    {
                        "GH_TOKEN": "fake-test-token",
                        "TAUCETI_GITHUB_SHARED_DIR": root,
                        "TAUCETI_WORKER_ID": "watch-test",
                        "TAUCETI_RECOVERY_CONTINUATION": recovery,
                    },
                    clear=True,
                ),
            ):
                response = subprocess.CompletedProcess(["gh", *args], exit_status, "run completed", "")
                with patch.object(tr, "_execute", return_value=response) as execute:
                    actual = tr.execute(["gh", *args])
                assert execute.call_count == 1, "Read must remain available during recovery"
                assert execute.call_args.kwargs["_intent"] is None, "Watch created a publication intent"
                assert actual.returncode == exit_status, "Do not hide a failed CI result"
                assert not list(outbox.intent_paths()), "A read must never remain in the outbox"

for action in ("cancel", "rerun", "delete"):
    args = ["run", action, "123", "--repo", "org/repo"]
    with (
        tempfile.TemporaryDirectory() as root,
        patch.dict(
            os.environ,
            {
                "GH_TOKEN": "fake-test-token",
                "TAUCETI_GITHUB_SHARED_DIR": root,
                "TAUCETI_WORKER_ID": "mutation-test",
            },
            clear=True,
        ),
    ):
        assert not tr.proxy_readonly(args), "A run mutation became read-only"
        intent = outbox.prepare(["gh", *args], os.environ)
        assert intent is not None and intent.exists(), "Real writes must still be retained"
        with patch.dict(os.environ, {"TAUCETI_RECOVERY_CONTINUATION": "1"}):
            with patch.object(tr, "_execute") as execute:
                denied = tr.execute(["gh", *args])
            execute.assert_not_called()
            assert denied.returncode != 0 and "cannot publish" in denied.stderr
print("PASS: successful/failed watches, recovery reads, and retained/denied run mutations; no network")
