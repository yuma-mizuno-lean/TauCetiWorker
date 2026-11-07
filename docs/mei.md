# Mei setup

This fork adds configured dependency-cache retrieval, shared cache reuse, and
worker reliability fixes to [upstream](https://github.com/TauCetiProject/TauCetiWorker).
Use Linux or WSL with `uv`, `git`, `gh`, `jq`, `elan`/`lake`, and your chosen agent CLI.
Authenticate GitHub and the agent with your own accounts.

```sh
gh auth login
codex login
uv tool install git+https://github.com/yuma-mizuno-lean/TauCetiWorker@main
tauceti --conf https://raw.githubusercontent.com/yuma-mizuno-lean/Mei/main/tauceti.toml doctor
```

Resolve doctor failures before starting. To run and stop a review-only worker:

```sh
tauceti --conf https://raw.githubusercontent.com/yuma-mizuno-lean/Mei/main/tauceti.toml workers add mei-reviewer --agent codex --only review
tauceti --conf https://raw.githubusercontent.com/yuma-mizuno-lean/Mei/main/tauceti.toml workers status
tauceti --conf https://raw.githubusercontent.com/yuma-mizuno-lean/Mei/main/tauceti.toml workers disable mei-reviewer
```

Use a unique worker ID; substitute `claude` if that is your authenticated agent.
Always pass `--conf`. Project review eligibility and quota limits still apply.
See [worker controls](workers.md) and [sandbox options](sandbox.md) for details.

The worker fetches caches automatically using standard `lake cache get` and Mei's
configuration. Contributors need no R2 upload key; Mei CI publishes the cache.
Downloads are incremental, not necessarily one request. The opted-in root cache
can fall back to compilation; dependency preparation failures still block work.

## Open Math OS agent

`--agent openmathos` runs Claude Code against the
[Open Math OS](https://os.openmathmodel.org/v1/doc/claude) gateway with your
Open Math OS key. `--agent claude` is unchanged and keeps using your Anthropic
account; nothing is written to `~/.claude/settings.json`. Store the key once,
without putting it on the command line:

```sh
install -m 600 /dev/null ~/.config/tauceti/openmathos.key
nano ~/.config/tauceti/openmathos.key   # paste the key, save
```

Then declare a worker, for example in `workers.toml`:

```toml
[[workers]]
id = "omos-author"
agent = "openmathos"
only = ["rebase", "fix-ci", "fix", "roadmap"]
author_model = "claude-openmathos-136586835026765720304391437666977767985"  # Kimi K3.1 Pro
conf = "https://raw.githubusercontent.com/yuma-mizuno-lean/Mei/main/tauceti.toml"
```

The agent is unpaced, runs on the host only and never reviews, because the review
engine would record its verdicts as Claude reviews. Each round first checks that
the gateway lists the exact `author_model` id. `OPENMATHOS_API_KEY`,
`OPENMATHOS_API_KEY_FILE` and `OPENMATHOS_BASE_URL` override the defaults. The
code lives in `tauceti_worker/openmathos.py`; other files only carry short hooks
marked `Mei fork`.

## Keeping the fork in sync

`main` is upstream `main` plus the Mei patches, joined by merge commits. Never
rebase or force-push it. To take a new upstream:

```sh
git fetch origin && git fetch fork
git worktree add -b sync/upstream-$(date +%Y%m%d) ../tw-sync fork/main
cd ../tw-sync && git merge origin/main     # resolve, keeping the fork's reduced CI
./tests/run-all -j "$(nproc)"
git push fork HEAD:main                    # fast-forward only
```

The operator checkout runs `fork/main` itself. Stop the manager, update it and restart:

```sh
tauceti workers manager-stop
git -C ~/TauCetiWorker pull --ff-only fork main
tauceti workers apply
```

Before merging, look for a fork patch that upstream has adopted and drop it. The
patches are: dependency-cache services and multi-package cache expansion
(`agents.py`, `expanded_cache.py`, `repair_recovery.py`), the exact history cutoff
(`activity.py`), read-only `gh run watch` (`github_transport.py`), the OAuth
User-Agent (`oauth.py`), the Pi OpenRouter login (`openrouter_auth.py`), and the
Open Math OS agent.

Upstream has no declared license at the inspected base revision; this fork does
not add or imply an Apache-2.0 license. See [GitHub's licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
