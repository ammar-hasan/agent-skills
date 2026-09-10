#!/usr/bin/env python3
"""Check portable skill packaging and catalog coverage before promotion."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="require a version increase for packaged files changed since this Git revision")
    parser.add_argument("--release-tag", help="verify a <skill-name>-v<version> release tag")
    args = parser.parse_args()
    if args.base:
        subprocess.run(["git", "rev-parse", "--verify", f"{args.base}^{{commit}}"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    errors = []
    folders = sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir())
    names = set()
    versions = {}
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
            metadata = meta.get("metadata", {})
            version = metadata.get("version") if isinstance(metadata, dict) else None
            if not isinstance(version, str) or not VERSION.fullmatch(version):
                errors.append(f"{label}: metadata.version must be a quoted MAJOR.MINOR.PATCH version")
            else:
                versions[folder.name] = version
                changelog = folder / "CHANGELOG.md"
                if not changelog.is_file() or not re.search(r"^## \[" + re.escape(version) + r"\] - \d{4}-\d{2}-\d{2}$", changelog.read_text(), re.M):
                    errors.append(f"{label}: changelog needs an entry for {version}")
                if args.base:
                    previous = subprocess.run(["git", "show", f"{args.base}:skills/{folder.name}/SKILL.md"], cwd=ROOT, text=True, capture_output=True)
                    if previous.returncode == 0:
                        old_match = re.match(r"\A---\n(.*?)\n---", previous.stdout, re.S)
                        old_meta = yaml.safe_load(old_match.group(1)) if old_match else {}
                        old_version = (old_meta.get("metadata") or {}).get("version")
                        changed = subprocess.check_output(["git", "diff", "--name-only", args.base, "--", f"skills/{folder.name}"], cwd=ROOT, text=True).strip()
                        if changed and isinstance(old_version, str) and VERSION.fullmatch(old_version):
                            if tuple(map(int, version.split('.'))) <= tuple(map(int, old_version.split('.'))):
                                errors.append(f"{label}: packaged changes require a version newer than {old_version}")
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
    for skill in catalog:
        if skill.get("version") != versions.get(skill["name"]):
            errors.append(f"Catalog version does not match {skill['name']} metadata")
    if args.release_tag and args.release_tag not in {f"{name}-v{version}" for name, version in versions.items()}:
        errors.append("Release tag must match a skill name and its metadata.version")
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
