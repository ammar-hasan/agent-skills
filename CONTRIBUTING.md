# Contributing

Thanks for helping make these skills more useful.

For a fix, explain the request or situation that failed and how your change improves the outcome. Include a reproducible example when possible. Keep unrelated improvements in separate pull requests.

## Promoting a skill

Only skills explicitly selected by a maintainer belong here. Propose a new skill in an issue or pull request with its purpose, a realistic example request, and its runtime requirements.

When a skill is selected:

1. Copy only that skill into `skills/<skill-name>/`. Exclude local Git history, caches, logs, credentials, and machine-specific state.
2. Keep a valid `SKILL.md` with a matching lowercase, hyphenated `name` and a useful `description`. Bundle all necessary scripts and references, with relative links.
3. Include a copy of the MIT license and preserve any applicable third-party attribution. Document dependencies and platform constraints.
4. Add the skill to the README and `site/catalog.json`, including a short explanation and an example request.
5. Run validation and the tests relevant to the skill, then open a pull request. Maintainers decide when it is ready to merge.

Avoid adding every globally installed skill or automatically syncing a personal skills directory. Keep the instructions focused on the task the skill actually solves.

Review every promoted file for private project names, local paths, internal URLs, account identifiers, credentials, and captured task data. Examples should be generic. Do not commit pane captures, session snapshots, resume manifests, or local state. Automated checks detect common patterns; they do not replace reading the files.

## Local checks

With Python 3.9+ and tmux installed:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/validate_skills.py
python3 scripts/check_public_content.py
python3 -m unittest discover -s skills/tmux-agent-orchestrator/tests -v
```

The integration tests create temporary tmux sessions and clean them up. They do not launch an AI agent. Without tmux, they are skipped; install tmux to exercise the helper.

For the catalog website, see [site/README.md](site/README.md).
