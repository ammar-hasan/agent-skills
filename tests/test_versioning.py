"""Exercise version checks against actual changes in an isolated Git repository."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class VersioningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / "skills/example-skill"
        self.skill.mkdir(parents=True)
        (self.root / "scripts").mkdir()
        (self.root / "site").mkdir()
        shutil.copyfile(ROOT / "scripts/validate_skills.py", self.root / "scripts/validate_skills.py")
        shutil.copyfile(ROOT / "LICENSE", self.root / "LICENSE")
        shutil.copyfile(ROOT / "LICENSE", self.skill / "LICENSE")
        (self.root / "README.md").write_text("[Example](skills/example-skill/SKILL.md)\n")
        self.write_version("1.0.0")
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("add", ".")
        self.git("commit", "-qm", "Initial fixture")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def write_version(self, version):
        (self.skill / "SKILL.md").write_text(
            f'---\nname: example-skill\ndescription: Handle a sample task.\nlicense: MIT\nmetadata:\n  version: "{version}"\n---\nSample instructions.\n'
        )
        (self.skill / "CHANGELOG.md").write_text(f"# Changelog\n\n## [{version}] - 2026-09-10\n\nUpdate.\n")
        (self.root / "site/catalog.json").write_text(json.dumps([{"name": "example-skill", "version": version}]))

    def validate(self, *args):
        return subprocess.run([sys.executable, "scripts/validate_skills.py", *args], cwd=self.root, capture_output=True, text=True)

    def test_packaged_change_requires_a_version_increase(self):
        (self.skill / "reference.txt").write_text("New packaged instructions.\n")
        self.git("add", ".")
        self.assertNotEqual(self.validate("--base", "HEAD").returncode, 0)
        self.write_version("1.0.1")
        result = self.validate("--base", "HEAD")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_catalog_mismatch_and_wrong_release_tag_are_rejected(self):
        self.assertNotEqual(self.validate("--release-tag", "example-skill-v2.0.0").returncode, 0)
        (self.root / "site/catalog.json").write_text('[{"name":"example-skill","version":"2.0.0"}]')
        self.assertNotEqual(self.validate().returncode, 0)

    def test_site_only_change_does_not_require_skill_version_bump(self):
        (self.root / "site/index.html").write_text("<h1>Catalog</h1>")
        self.git("add", ".")
        result = self.validate("--base", "HEAD", "--release-tag", "example-skill-v1.0.0")
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
