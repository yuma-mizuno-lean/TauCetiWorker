# Using this fork with Mei

## Scope

Upstream base: `8bd7ded5b309e0155c523b1dec52d021c6327cbe`.
Runtime and tests match the verified deployment `5eafcd4f779cb0c77144bb0ed23fe841deedf598`.
The deployment passed 128 test scripts; the upstream runner excludes
`egress.sh` and `integration_repair_fixture.py`, and platform-specific subtests can skip.
The old emergency snapshot mechanism and per-round configuration reload patches
are not included. Local fleet definitions and local operation history are not published.

## Install

Use Linux or WSL with Python 3.11+, `uv`, `git`, `gh`, `jq`, and `elan`/`lake`.
Install and authenticate the agent CLI you intend to use. Each contributor uses
their own accounts; no shared maintainer credentials are required.

```sh
gh auth login
# Authenticate the agent you intend to run, for example: codex login
uv tool install git+https://github.com/yuma-mizuno-lean/TauCetiWorker@main
tauceti --conf https://raw.githubusercontent.com/yuma-mizuno-lean/Mei/main/tauceti.toml doctor
```

Resolve the doctor checks before starting work. GitHub authentication alone does
not grant project review eligibility: the configured review service and project
policy still apply. For a reproducible installation, replace `main` with a
published commit SHA. The Python dependency on upstream TauCetiTools is already
pinned in `pyproject.toml`; a separate local Tools checkout is not required.

## Review only

The following starts a persistent Codex reviewer. Use a worker ID that is unique
in your local manager; substitute `claude` when that is your authenticated agent.
The add command starts the worker immediately.

```sh
tauceti --conf https://raw.githubusercontent.com/yuma-mizuno-lean/Mei/main/tauceti.toml workers add mei-reviewer --agent codex --only review
tauceti --conf https://raw.githubusercontent.com/yuma-mizuno-lean/Mei/main/tauceti.toml workers status
tauceti --conf https://raw.githubusercontent.com/yuma-mizuno-lean/Mei/main/tauceti.toml workers disable mei-reviewer
```

Always pass `--conf`: omitting it selects the upstream default project. The local
manager persists configuration in `~/.config/tauceti/workers.toml`; do not commit
that file. A live process can be waiting for quota or eligible work; `alive` does
not mean a review has started. See [worker controls](workers.md) and
[sandbox choices](sandbox.md) before running agents.

## Cache behavior

The worker uses standard `lake cache get` with endpoints from the trusted project
configuration. It retrieves configured dependencies at the revisions in
`lake-manifest.json` and uses the same configuration during recovery verification.
Public downloads need no R2 upload key. Cache publication belongs to the project's
CI, not to each contributor's worker.

For configurations explicitly setting `services.cache.worker_public = true`, a
root-project cache failure falls back to compilation. Lookup is bounded to 20
revisions, each root-cache command is limited to 120 seconds, and an error is not
retried immediately. Mathlib and configured dependency preparation retain blocking
failure handling. Verified archives and revision maps are shared on the same host.
The cache is incremental: a cold host can download multiple artifacts; these
bounds do not promise one HTTP request or a guaranteed Cloudflare free-tier total.

## Downstream changes and maintenance

- Configured dependency caches, shared verified artifacts across packages,
  bounded optional root-cache reads, and the archive lock-slot collision fix.
- Explicit OAuth refresher User-Agent, with offline request-contract tests.
- Read-only `gh run watch` handling rather than retained publication attempts.
- Exact activity cutoff timestamps, plus an isolated quota dispatch test.

Keep upstream history and merge upstream changes normally. Remove a downstream
fix when an upstream equivalent is verified; keep repository-specific endpoints
in Mei's `tauceti.toml`, not in Worker source. This fork runs CI on standard GitHub
Ubuntu runners and has no scheduled provider probes.

## Licensing status

The inspected upstream revision contains no license file or declared package
license. This fork preserves that status and does not relicense upstream code.
GitHub permits viewing and forking public repositories on its service; this is
not a claim of an Apache-2.0 or other general reuse license for Worker.
See [GitHub's licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
