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
without an editor and without putting it on the command line:

```sh
install -m 600 /dev/null ~/.config/tauceti/openmathos.key
read -rs KEY && printf '%s\n' "$KEY" > ~/.config/tauceti/openmathos.key && unset KEY
```

The model has no default: the gateway's ids are opaque and may change, so set the
exact id once, as `author_model`. List the ids with
`curl -s -H "Authorization: Bearer $(cat ~/.config/tauceti/openmathos.key)" https://os.openmathmodel.org/claude/v1/models`.

```toml
[[workers]]
id = "openmathos-fix"
agent = "openmathos"
only = ["rebase", "fix-ci", "fix"]
author_model = "EXACT_GATEWAY_MODEL_ID"
conf = "https://raw.githubusercontent.com/yuma-mizuno-lean/Mei/main/tauceti.toml"

[[workers]]
id = "openmathos-review"
agent = "openmathos"
only = ["review"]
author_model = "EXACT_GATEWAY_MODEL_ID"
conf = "https://raw.githubusercontent.com/yuma-mizuno-lean/Mei/main/tauceti.toml"
```

The same model authors and reviews. Reviews go through the review engine's
`openmathos` reviewer, which the project's `[tools.review]` pin provides (Mei pins
`yuma-mizuno-lean/TauCetiReview`); the worker passes the model as
`--openmathos-model`, and labels show the model the gateway reports. The worker
reads the key file before isolating each worker's HOME and hands it on as
`OPENMATHOS_API_KEY`; that variable, if set, wins over the file
(`OPENMATHOS_API_KEY_FILE` names another file). The agent is unpaced and runs on
the host only. Each round first checks that the gateway lists the exact model.
The code lives in `tauceti_worker/openmathos.py`; other files only carry short
hooks marked `Mei fork`.

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

The review engine fork, `yuma-mizuno-lean/TauCetiReview`, is kept the same way:
merge upstream `main` into the fork's `main`, run its tests, and push. Its only
patch is the Open Math OS reviewer (`runner/openmathos.py` plus hooks marked
`Mei fork`, and the `review_repository` input of the merge workflows). Then move
every engine pin in Mei to the new fork commit in one PR: `[tools.review]` in
`tauceti.toml` and the workflows that name the engine.

Upstream has no declared license at the inspected base revision; this fork does
not add or imply an Apache-2.0 license. See [GitHub's licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
