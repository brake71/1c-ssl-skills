import copy
import json
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

from ci import native_eval as native
from ci import run_skill_evals as runner


class SecondaryReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.references = self.root / "references"
        self.references.mkdir()
        for name in ("users-access.md", "base-common.md"):
            (self.references / name).write_text(name, encoding="utf-8")

    def corpus(self, secondary=..., reference="users-access.md", trigger=True):
        case = {
            "id": "activation", "task": "Task", "reference": reference,
            "should_trigger": trigger, "required_patterns": ["answer"],
            "secondary_references": [] if secondary is ... else secondary,
        }
        path = self.root / "cases.json"
        path.write_text(json.dumps({"version": 1, "cases": [case]}), encoding="utf-8")
        return path

    def matrix(self, rows, unscoped=None):
        path = self.root / "matrix.json"
        path.write_text(json.dumps({"version": 1, "references": rows,
                                    "unscoped_cases": unscoped or []}), encoding="utf-8")
        return runner.load_reference_matrix(path)

    def test_optional_secondary_field_and_safe_validation(self):
        case = runner.load_cases(self.corpus())[0]
        self.assertEqual(case.secondary_references, ())
        self.assertEqual(case.required_references, ("users-access.md",))
        self.assertEqual(runner.load_cases(self.corpus(["base-common.md"]))[0].required_references,
                         ("users-access.md", "base-common.md"))
        for secondary, reference, trigger in (
            ([], "../users-access.md", True), ([], ["users-access.md"], True),
            ([], "", True), ([], "dir/users-access.md", True),
            (["dir\\file.md"], "users-access.md", True),
            ("base-common.md", "users-access.md", True), (["../evil.md"], "users-access.md", True),
            (["dir/file.md"], "users-access.md", True), (["users-access.md"], "users-access.md", True),
            (["base-common.md", "base-common.md"], "users-access.md", True),
            (["base-common.md"], None, True), (["base-common.md"], "users-access.md", False),
        ):
            with self.subTest(secondary=secondary, reference=reference, trigger=trigger):
                with self.assertRaises(runner.EvalError):
                    runner.load_cases(self.corpus(secondary, reference, trigger))

    def test_matrix_accepts_primary_only_and_primary_plus_secondary(self):
        cases = runner.load_cases(self.corpus(["base-common.md"]))
        for rows in (
            {"users-access.md": ["activation"], "base-common.md": ["activation"]},
            {"users-access.md": ["activation"], "base-common.md": []},
        ):
            # The legacy primary-only form is valid only when no secondary is declared.
            if not rows["base-common.md"]:
                cases = runner.load_cases(self.corpus())
            with self.subTest(rows=rows):
                refs, unscoped = self.matrix(rows)
                runner.validate_reference_matrix(cases, refs, unscoped, self.references)

    def test_matrix_rejects_missing_secondary_extra_and_duplicate_row_assignment(self):
        cases = runner.load_cases(self.corpus(["base-common.md"]))
        refs, unscoped = self.matrix({"users-access.md": ["activation"], "base-common.md": []})
        with self.assertRaisesRegex(runner.EvalError, "assignments"):
            runner.validate_reference_matrix(cases, refs, unscoped, self.references)
        refs, unscoped = self.matrix({"users-access.md": ["activation"], "base-common.md": ["activation"],
                                      "other.md": []})
        with self.assertRaisesRegex(runner.EvalError, "unknown files"):
            runner.validate_reference_matrix(cases, refs, unscoped, self.references)
        refs, unscoped = self.matrix({"users-access.md": ["activation", "activation"],
                                      "base-common.md": ["activation"]})
        with self.assertRaisesRegex(runner.EvalError, "duplicate case"):
            runner.validate_reference_matrix(cases, refs, unscoped, self.references)

    def test_pre_fixture_manifest_resume_is_rejected(self):
        for version in (5, 6):
            with self.subTest(version=version), self.assertRaisesRegex(runner.EvalError, "schema_version=7"):
                runner.validate_resume_report({"schema_version": version}, {})

    def _events(self, names):
        return [native.normalized_item({
            "id": name, "type": "commandExecution",
            "command": f"rg -n . .agents/skills/bsp/references/{name}",
            "exitCode": 0, "aggregatedOutput": name,
        }) for name in names]

    def test_reference_evidence_requires_every_file_and_retains_per_file_data(self):
        case = runner.load_cases(self.corpus(["base-common.md"]))[0]
        all_reads = self._events(case.required_references)
        by_file, union = runner.reference_read_evidence(all_reads, "bsp", case.required_references)
        self.assertTrue(all(by_file.values()))
        self.assertTrue(union)
        primary_only = self._events(["users-access.md"])
        by_file, _ = runner.reference_read_evidence(primary_only, "bsp", case.required_references)
        self.assertTrue(by_file["users-access.md"])
        self.assertFalse(by_file["base-common.md"])
        failed_secondary = self._events(["users-access.md", "base-common.md"])
        failed_secondary[1]["item"]["exit_code"] = 1
        by_file, _ = runner.reference_read_evidence(failed_secondary, "bsp", case.required_references)
        self.assertFalse(by_file["base-common.md"])
        listing = native.normalized_item({
            "id": "listing", "type": "commandExecution",
            "command": "dir .agents/skills/bsp/references/base-common.md",
            "exitCode": 0, "aggregatedOutput": "base-common.md",
        })
        by_file, _ = runner.reference_read_evidence(
            primary_only + [listing], "bsp", case.required_references
        )
        self.assertFalse(by_file["base-common.md"])

    def test_both_transports_report_all_and_primary_only_reads(self):
        case = runner.load_cases(self.corpus(["base-common.md"]))[0]
        self.root.mkdir(exist_ok=True)
        auth = {"auth_mode": "chatgpt", "tokens": {"access_token": "secret", "account_id": "acct"}}
        (self.root / "auth.json").write_text(json.dumps(auth), encoding="utf-8")
        snapshot = {"skills": [], "config_sha256": "cfg"}
        for names, expected in ((case.required_references, True), (("users-access.md",), False)):
            events = self._events(names)
            with self.subTest(names=names):
                with patch.object(runner, "extract_jsonl", return_value=(events, [])), \
                        patch.object(runner.subprocess, "run", return_value=SimpleNamespace(
                            stdout="", stderr="", returncode=0)):
                    exec_result = runner.run_cdx("cdx", case, self.root, self.root, "red", 1,
                                                 "model", None, 1, "bsp")
                class Client:
                    process = SimpleNamespace(pid=123)
                    def call(self, method, params):
                        return {"account": {"type": "chatgpt"}}
                    def close(self):
                        pass
                client = Client()
                with patch.object(native.probe, "NativeClient", return_value=client), \
                        patch.object(native.probe, "initialize_native", return_value={}), \
                        patch.object(native.probe, "capture_snapshot", side_effect=[
                            (copy.deepcopy(snapshot), {"thread": {"id": "thread"}}),
                            (copy.deepcopy(snapshot), {"thread": {"id": "thread"}}),
                        ]), \
                        patch.object(native, "collect_turn", return_value=(
                            events + [{"type": "item.completed", "item": {"type": "agent_message", "text": "answer"}}],
                            [], {"status": "completed"}, "turn",
                        )):
                    native_result = native.run_native(
                        "cdx", case, self.root, self.root, "red", 1, "model", "medium", 1,
                        "bsp", self.root, "source", native.auth_identity(auth),
                    )
                self.assertEqual(exec_result["expected_reference_read"], expected)
                self.assertEqual(native_result["expected_reference_read"], expected)
                self.assertEqual(set(exec_result["reference_reads"]), set(case.required_references))
                self.assertEqual(set(native_result["reference_evidence_by_file"]), set(case.required_references))


if __name__ == "__main__":
    unittest.main()
