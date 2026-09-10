# Working in this repository

- This is a curated skills collection. Promote only skills the user or a maintainer selects; do not sync global skill directories wholesale.
- Keep installable skills self-contained under `skills/<name>/`, with portable paths and valid `SKILL.md` metadata.
- Preserve a promoted skill’s behavior unless a requested change or verified defect calls for an update.
- Keep `README.md` and `site/catalog.json` aligned with the available skills and their actual requirements.
- Run `python3 scripts/validate_skills.py` with the development dependencies installed, and relevant existing helper tests after skill changes. For site changes, run the build in `site/`.
- Never commit nested Git repositories, local credentials, logs, or caches.
- Host the catalog on GitHub Pages. Do not create deployments with other hosting providers.
- Run `python3 scripts/check_public_content.py` before publishing. Review examples for private project details that pattern checks cannot recognize; keep captures and snapshots out of the repository.
- Version skills independently. Packaged changes need a version increase in `SKILL.md`, a changelog entry, and a matching catalog version. Release tags use `<skill-name>-v<version>` and must never be moved or reused.
