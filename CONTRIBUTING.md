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

## Versioning and releases

Skills are versioned independently using `MAJOR.MINOR.PATCH` in the quoted `metadata.version` field of `SKILL.md`. The website package version is separate.

- **Patch:** compatible fixes, clarifications, or changes to bundled references and tests.
- **Minor:** new capabilities that preserve existing usage.
- **Major:** incompatible workflow, command, or required-environment changes.

When changing any packaged skill file, increase its version, add a dated entry in its `CHANGELOG.md`, and update its version in `site/catalog.json`. CI checks these agree and requires changed skills to increase their version. New skills start at `1.0.0` when ready for their first stable release.

Publish from a clean checkout after the main-branch checks pass. Create an annotated tag named `<skill-name>-v<version>`, then a GitHub Release with notes for that version. Validate the exact tag name first:

```sh
python scripts/validate_skills.py --release-tag tmux-agent-orchestrator-v1.0.0
```

Never move or reuse a published version tag. Publish a new version for corrections. Release URLs let users install a specific version; the repository shorthand tracks `main`. Installing another version is an explicit update, and `skills update` should not be treated as a guarantee that an installation remains pinned.

Global installations are copies of published releases. Make changes in this repository, validate and release them, then reinstall the selected version. Do not develop inside the installed global copy.
