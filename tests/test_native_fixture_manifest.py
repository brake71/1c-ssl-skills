"""Prospective native fixture integrity and resume controls (no model calls)."""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ci import native_eval as native
from ci import run_skill_evals as runner


class NativeFixtureManifestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.workdir = self.root / "consumer"
        self.workdir.mkdir()
        subprocess.run(["git", "init", "-q", str(self.workdir)], check=True)
        (self.workdir / "task.txt").write_text("initial", encoding="utf-8")
        self.stage = self.workdir / ".agents" / "skills" / "bsp"
        self.output = self.root / "report.json"
        self.auth = self.root / "auth.json"
        self.auth.write_text(json.dumps({"auth_mode": "chatgpt", "tokens": {
            "access_token": "secret", "refresh_token": "secret", "id_token": "secret",
            "account_id": "test-account",
        }}), encoding="utf-8")

    def manifest(self):
        return runner.ordinary_fixture_manifest(self.workdir, self.stage)

    def report(self, baseline=True):
        case_id = "message-bound-to-field"
        def record(passed):
            return {"status": "completed" if passed else "quality_failed",
                    "response": "cached", "returncode": 0, "usage": {},
                    "skill_activated": passed, "expected_reference_read": passed,
                    "score": {"passed": passed, "invalid_methods": [],
                              "unsafe_calls": [], "forbidden_hits": []}}
        return {
            "schema_version": runner.REPORT_SCHEMA_VERSION, "launcher": "unused", "transport": "native",
            "transport_profile": native.PROFILE,
            "native_helper_sha256": runner.file_sha256(Path(native.__file__)),
            "native_probe_sha256": runner.file_sha256(Path(native.probe.__file__)),
            "auth_identity_sha256": native.auth_identity(native.load_auth(self.auth)),
            "model": "model", "reasoning_effort": "medium", "skill": str(runner.DEFAULT_SKILL),
            "workdir": str(self.workdir), "bsl_src": None, "selected_cases": [case_id],
            "corpus_sha256": runner.file_sha256(runner.DEFAULT_CASES),
            "reference_matrix_sha256": runner.file_sha256(runner.DEFAULT_REFERENCE_MATRIX),
            "skill_sha256": runner.skill_sha256(runner.DEFAULT_SKILL),
            "runner_sha256": runner.file_sha256(Path(runner.__file__)), "runs": 1,
            "phases_requested": ["red", "green"], "min_pass_rate": 0.8,
            "min_activation_rate": 0.8, "ordinary_fixture_baseline": self.manifest() if baseline else None,
            "complete": True, "gate": {"passed": True}, "isolation_gate": {"passed": True},
            "report_path": str(self.output), "phases": {
                "red": {"run_matrix": {case_id: [record(False)]}},
                "green": {"run_matrix": {case_id: [record(True)]}},
            },
        }

    def invoke(self, resume=True, matrix=None, drift_after_cleanup=False):
        from contextlib import contextmanager
        @contextmanager
        def home(_auth):
            yield self.root
        args = ["runner", "--transport", "native", "--dir", str(self.workdir),
                "--case", "message-bound-to-field", "--bsl-src", "",
                "--auth-file", str(self.auth), "--runs", "1", "--model", "model",
                "--reasoning-effort", "medium", "--output", str(self.output)]
        if resume:
            args.append("--resume")
        snapshot = {"auth_identity_sha256": native.auth_identity(native.load_auth(self.auth))}
        snapshots = []
        def restored(*_args):
            snapshots.append(True)
            if drift_after_cleanup and len(snapshots) == 2:
                (self.workdir / "task.txt").write_text("mutated after cleanup")
            return snapshot
        with patch.object(sys, "argv", args), \
                patch.object(runner, "resolve_cdx", return_value="unused"), \
                patch.object(runner, "find_conflicting_skills", return_value=[]), \
                patch.object(runner, "load_method_index", return_value={}), \
                patch.object(native, "authenticated_home", side_effect=home), \
                patch.object(native, "restored_snapshot", side_effect=restored), \
                patch.object(native, "phase_inventory_reasons", return_value=[]), \
                patch.object(native, "report_inventory_reasons", return_value=[]), \
                patch.object(native, "run_native") as model, \
                patch("sys.stderr", new=io.StringIO()):
            if matrix is None:
                runner.main()
            else:
                with patch.object(runner, "execute_run_matrix", side_effect=matrix):
                    runner.main()
            model.assert_not_called()

    def test_exact_stage_and_git_excluded_but_other_skills_count(self):
        (self.workdir / ".git" / "ignored").write_text("meta")
        self.stage.mkdir(parents=True)
        (self.stage / "SKILL.md").write_text("staged")
        other = self.stage.parent / "other" / "SKILL.md"
        other.parent.mkdir()
        other.write_text("other")
        baseline = self.manifest()
        self.assertEqual(set(baseline), {"task.txt", ".agents/skills/other/SKILL.md"})
        (self.stage / "SKILL.md").write_text("changed")
        self.assertEqual(self.manifest(), baseline)
        other.write_text("changed")
        self.assertNotEqual(self.manifest(), baseline)

    def test_ordinary_symlink_refused(self):
        try:
            (self.workdir / "linked").symlink_to(self.root / "auth.json")
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaisesRegex(runner.EvalError, "Linked ordinary"):
            self.manifest()

    def test_unchanged_fixture_resumes_cached_outcomes(self):
        self.output.write_text(json.dumps(self.report()), encoding="utf-8")
        self.invoke()
        result = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertTrue(result["gate"]["passed"])
        self.assertTrue(result["ordinary_fixture_gate"]["passed"])
        self.assertEqual(result["ordinary_fixture_checks"]["after_native_cleanup"], self.manifest())
        self.assertFalse(self.stage.exists())

    def test_changed_or_missing_baseline_blocks_resume_before_model_and_write(self):
        for change in ("mutated", "missing", "added", "removed"):
            with self.subTest(change=change):
                report = self.report(baseline=change != "missing")
                self.output.write_text(json.dumps(report), encoding="utf-8")
                if change == "mutated":
                    (self.workdir / "task.txt").write_text("different")
                elif change == "added":
                    (self.workdir / "extra.txt").write_text("new")
                elif change == "removed":
                    (self.workdir / "task.txt").unlink()
                before = self.output.read_bytes()
                with self.assertRaises(SystemExit) as caught:
                    self.invoke()
                self.assertEqual(caught.exception.code, 2)
                self.assertEqual(self.output.read_bytes(), before)
                self.assertFalse(self.stage.exists())
                (self.workdir / "task.txt").write_text("initial")
                (self.workdir / "extra.txt").unlink(missing_ok=True)

    def test_post_cleanup_drift_fails_isolation_gate(self):
        self.output.write_text(json.dumps(self.report()), encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            self.invoke(drift_after_cleanup=True)
        self.assertEqual(caught.exception.code, 1)
        result = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertTrue(result["complete"])
        self.assertFalse(result["ordinary_fixture_gate"]["passed"])
        self.assertFalse(result["isolation_gate"]["passed"])
        self.assertFalse(result["gate"]["passed"])
        self.assertFalse(self.stage.exists())

    def test_existing_staging_is_rejected_before_model(self):
        self.stage.mkdir(parents=True)
        (self.stage / "sentinel").write_text("user-owned")
        with self.assertRaises(SystemExit) as caught:
            self.invoke(resume=False)
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual((self.stage / "sentinel").read_text(), "user-owned")

    def test_mutation_after_green_cleanup_is_recorded(self):
        count = []
        def fake_matrix(cases, runs, jobs, execute, **kwargs):
            phase = "red" if not count else "green"
            count.append(phase)
            if phase == "green":
                (self.workdir / "task.txt").write_text("mutated")
            return [[self.report()["phases"][phase]["run_matrix"][cases[0].id][0]]]
        with self.assertRaises(SystemExit) as caught:
            self.invoke(resume=False, matrix=fake_matrix)
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(count, ["red", "green"])
        result = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertFalse(result["ordinary_fixture_gate"]["passed"])
        self.assertNotIn("gate", result)
        self.assertFalse(self.stage.exists())

    def test_mutation_after_red_stops_before_green(self):
        count = []
        def fake_matrix(cases, runs, jobs, execute, **kwargs):
            count.append("red")
            (self.workdir / "task.txt").write_text("mutated")
            return [[self.report()["phases"]["red"]["run_matrix"][cases[0].id][0]]]
        with self.assertRaises(SystemExit) as caught:
            self.invoke(resume=False, matrix=fake_matrix)
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(count, ["red"])
        result = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertNotEqual(result["ordinary_fixture_baseline"], result["ordinary_fixture_checks"]["after_red_cleanup"])
        self.assertFalse(result["complete"])
        self.assertFalse(self.stage.exists())


if __name__ == "__main__":
    unittest.main()
