import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import zipfile

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = REPO_ROOT / "ci" / "build_release.py"
spec = importlib.util.spec_from_file_location("build_release_for_tests", BUILDER_PATH)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuildReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Build Test")
        self.git("config", "core.autocrlf", "true")
        self.source_files = {
            "skills/bsp/SKILL.md": b"# BSP\nskill\n",
            "skills/bsp/agents/openai.yaml": b"name: bsp\nprompt: hello\n",
            "skills/bsp/references/example.md": "Текст\n".encode("utf-8"),
            "skills/bsp/scripts/tool.py": b"print('ok')\n",
            "skills/bsp/__pycache__/tracked.pyc": b"compiled cache",
            "install.sh": b"#!/bin/sh\necho ok\n",
            "install.ps1": b"Write-Output ok\n",
        }
        for name, content in self.source_files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        # Force Git's checkout filter to materialize CRLF rather than leaving
        # the LF bytes that were present when the file was initially staged.
        yaml = self.repo / "skills/bsp/agents/openai.yaml"
        yaml.unlink()
        self.git("checkout", "--", "skills/bsp/agents/openai.yaml")
        self.ref = self.git("rev-parse", "HEAD").strip()

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.PIPE).decode().strip()

    def test_reads_git_bytes_and_modes_ignoring_checkout_noise_and_is_deterministic(self):
        # autocrlf changes the checked-out bytes; untracked files and Python caches are excluded.
        yaml = self.repo / "skills/bsp/agents/openai.yaml"
        self.assertIn(b"\r\n", yaml.read_bytes())
        (self.repo / "skills/bsp/__pycache__").mkdir(exist_ok=True)
        (self.repo / "skills/bsp/__pycache__/junk.pyc").write_bytes(b"junk")
        (self.repo / "skills/bsp/untracked.md").write_bytes(b"untracked")
        out1, out2 = self.root / "one", self.root / "two"
        first = builder.build(self.ref, "v1.2", out1, self.repo)
        second = builder.build(self.ref, "v1.2", out2, self.repo)
        self.assertEqual(first["archives"], second["archives"])
        expected_files = set(self.source_files) - {"skills/bsp/__pycache__/tracked.pyc"}
        self.assertEqual(first["files"].keys(), expected_files)
        self.assertEqual((out1 / "extracted/skills/bsp/agents/openai.yaml").read_bytes(), self.source_files["skills/bsp/agents/openai.yaml"])
        self.assertEqual(first["skill_fingerprint"], builder.skill_fingerprint(self.source_files))
        for archive_name in first["archives"]:
            self.assertEqual((out1 / archive_name).read_bytes(), (out2 / archive_name).read_bytes())
        with zipfile.ZipFile(out1 / "bsp-skill-v1.2.zip") as archive:
            self.assertEqual(archive.namelist(), sorted(expected_files))
            self.assertEqual(archive.read("skills/bsp/agents/openai.yaml"), self.source_files["skills/bsp/agents/openai.yaml"])
            self.assertEqual((archive.getinfo("install.sh").external_attr >> 16) & 0o777, 0o755)
        with tarfile.open(out1 / "bsp-skill-v1.2.tar.gz", "r:gz") as archive:
            members = {member.name: member for member in archive.getmembers()}
            self.assertEqual(set(members), expected_files)
            self.assertEqual(members["install.sh"].mode, 0o755)
            self.assertEqual(archive.extractfile("skills/bsp/agents/openai.yaml").read(), self.source_files["skills/bsp/agents/openai.yaml"])
        manifest = json.loads((out1 / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_tree"], self.git("rev-parse", f"{self.ref}^{{tree}}"))
        self.assertEqual(manifest["archives"]["bsp-skill-v1.2.zip"], hashlib.sha256((out1 / "bsp-skill-v1.2.zip").read_bytes()).hexdigest())

    def test_refuses_existing_output_and_unsafe_version(self):
        output = self.root / "existing"
        output.mkdir()
        with self.assertRaisesRegex(builder.BuildError, "already exists"):
            builder.build(self.ref, "v1", output, self.repo)
        for version in ("../v1", "v1/evil", "v1;echo", "latest", "v1\\evil"):
            with self.subTest(version=version), self.assertRaisesRegex(builder.BuildError, "Invalid version"):
                builder.build(self.ref, version, self.root / ("out-" + str(len(version))), self.repo)

    def test_missing_required_file_is_rejected_without_output(self):
        self.git("rm", "skills/bsp/agents/openai.yaml")
        self.git("commit", "-qm", "remove required")
        output = self.root / "missing-output"
        with self.assertRaisesRegex(builder.BuildError, "Missing required Git paths"):
            builder.build("HEAD", "v1", output, self.repo)
        self.assertFalse(output.exists())

    def test_unsafe_git_mode_is_rejected(self):
        object_id = subprocess.check_output(
            ["git", "-C", str(self.repo), "hash-object", "-w", "--stdin"],
            input=b"../outside", stderr=subprocess.PIPE,
        ).decode().strip()
        self.git("update-index", "--add", "--cacheinfo", f"120000,{object_id},skills/bsp/unsafe-link")
        self.git("commit", "-qm", "add unsafe symlink mode")
        with self.assertRaisesRegex(builder.BuildError, "Unsafe Git object mode/type"):
            builder.build("HEAD", "v1", self.root / "unsafe-output", self.repo)

    def test_manifest_matches_eval_runner_fingerprint(self):
        path = REPO_ROOT / "ci" / "run_skill_evals.py"
        eval_spec = importlib.util.spec_from_file_location("runner_for_build_release_tests", path)
        runner = importlib.util.module_from_spec(eval_spec)
        import sys
        sys.modules[eval_spec.name] = runner
        eval_spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "skill"
            for name, data in self.source_files.items():
                if name.startswith("skills/bsp/"):
                    relative = name[len("skills/bsp/"):]
                    path = target / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            self.assertEqual(builder.skill_fingerprint(self.source_files), runner.skill_sha256(target))


if __name__ == "__main__":
    unittest.main()
