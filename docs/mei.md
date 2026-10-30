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

Upstream has no declared license at the inspected base revision; this fork does
not add or imply an Apache-2.0 license. See [GitHub's licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
