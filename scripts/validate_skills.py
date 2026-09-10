#!/usr/bin/env python3
"""Check portable skill packaging and catalog coverage before promotion."""

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors = []
    folders = sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir())
    names = set()
    allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    for folder in folders:
        entry = folder / "SKILL.md"
        label = str(folder.relative_to(ROOT))
        try:
            source = entry.read_text()
            match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", source, re.S)
            if not match:
                raise ValueError("SKILL.md requires YAML frontmatter")
            meta = yaml.safe_load(match.group(1))
            if not isinstance(meta, dict):
                raise ValueError("frontmatter must be a mapping")
            name = meta.get("name")
            if name != folder.name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", folder.name) or len(folder.name) > 64:
                errors.append(f"{label}: name must match a valid skill directory name")
            names.add(folder.name)
            for field, limit in [("description", 1024), ("compatibility", 500)]:
                value = meta.get(field)
                if field == "compatibility" and value is None:
                    continue
                if not isinstance(value, str) or not value.strip() or len(value) > limit:
                    errors.append(f"{label}: invalid {field}")
            if set(meta) - allowed:
                errors.append(f"{label}: unsupported frontmatter fields")
            if meta.get("license") != "MIT" or (folder / "LICENSE").read_text() != (ROOT / "LICENSE").read_text():
                errors.append(f"{label}: include matching MIT license metadata and notice")
            for link in re.findall(r"\]\(([^)]+)\)", source):
                if re.match(r"[a-z]+://|#", link):
                    continue
                target = (folder / link.split("#")[0]).resolve()
                if folder.resolve() not in target.parents or not target.exists():
                    errors.append(f"{label}: missing or nonportable reference {link}")
            for path in folder.rglob("*"):
                if path.is_symlink() or path.name in {".git", ".env"}:
                    errors.append(f"{label}: do not package {path.relative_to(folder)}")
        except (OSError, ValueError, yaml.YAMLError) as error:
            errors.append(f"{label}: {error}")
    catalog = json.loads((ROOT / "site/catalog.json").read_text())
    catalog_names = [skill["name"] for skill in catalog]
    if set(catalog_names) != names or len(catalog_names) != len(set(catalog_names)):
        errors.append("Catalog must contain exactly one entry for every promoted skill")
    readme = (ROOT / "README.md").read_text()
    for name in names:
        if f"skills/{name}/SKILL.md" not in readme:
            errors.append(f"README is missing the {name} catalog link")
    if not names:
        errors.append("No skills found")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Validated {len(names)} skill(s): metadata, bundled license, references, and catalog coverage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
