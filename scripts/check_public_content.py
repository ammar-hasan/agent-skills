#!/usr/bin/env python3
"""Catch common private data in publishable files without printing the data."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "personal filesystem path": re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+/|[A-Za-z]:\\Users\\[A-Za-z0-9_.-]+\\"),
    "credential-like token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-(?:proj-)?[A-Za-z0-9_-]{30,}|AKIA[A-Z0-9]{16}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "private hosting identifier": re.compile(r"appg(?:prj|repo|ver|dep)_[a-z0-9]+|(?:[a-z0-9-]+\.)+chatgpt\.site\b"),
    "personal email address": re.compile(r"[\w.+-]+@(?:gmail|hotmail|outlook)\.[a-z]+"),
}


def findings(path, data):
    problems = []
    if path.name.startswith(".env") or path.suffix in {".pem", ".key", ".log"}:
        problems.append("local configuration, key, or log file")
    content = data.decode("utf-8", errors="replace")
    for label, pattern in PATTERNS.items():
        if pattern.search(content):
            problems.append(label)
    if path.suffix == ".json":
        try:
            payload = json.loads(content)
            if isinstance(payload, dict) and {"sessions", "windows", "panes"} <= payload.keys():
                problems.append("tmux session snapshot")
        except ValueError:
            pass
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, help="also inspect a static website export")
    args = parser.parse_args()
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    ).decode().split("\0")
    paths = {ROOT / name for name in names if name}
    if args.artifact_dir:
        artifact = args.artifact_dir.resolve()
        if not (artifact / "index.html").is_file():
            parser.error("artifact directory must contain index.html")
        paths.update(artifact.rglob("*"))
    errors = []
    checked = 0
    for path in sorted(paths):
        if path.is_symlink():
            errors.append((path, "symlink in publishable files"))
        elif path.is_file():
            checked += 1
            errors.extend((path, issue) for issue in findings(path, path.read_bytes()))
            if args.artifact_dir and path.suffix == ".map" and artifact in path.parents:
                errors.append((path, "browser source map in static export"))
    for path, issue in errors:
        label = path.relative_to(ROOT) if ROOT in path.parents else path.name
        print(f"{label}: {issue}", file=sys.stderr)
    if errors:
        return 1
    print(f"Public-content check passed for {checked} files. Review examples separately for private project details.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
