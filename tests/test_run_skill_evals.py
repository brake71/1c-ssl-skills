import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "ci" / "run_skill_evals.py"
SKILL_DIR = REPO_ROOT / "skills" / "bsp"
FIXTURE_SRC = REPO_ROOT / "tests" / "fixtures" / "cf"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = load_module(RUNNER_PATH, "run_skill_evals_for_tests")


class EvalCorpusTests(unittest.TestCase):
    def test_repository_corpus_is_valid(self):
        cases = runner.load_cases(REPO_ROOT / "evals" / "cases.json")
        self.assertGreaterEqual(len(cases), 12)
        self.assertTrue(any(not case.should_trigger for case in cases))
        self.assertEqual(len(cases), len({case.id for case in cases}))

    def test_repository_reference_matrix_matches_corpus_and_skill(self):
        cases = runner.load_cases(REPO_ROOT / "evals" / "cases.json")
        references, unscoped = runner.load_reference_matrix(
            REPO_ROOT / "evals" / "reference-matrix.json"
        )
        matrix = runner.validate_reference_matrix(
            cases, references, unscoped, SKILL_DIR / "references"
        )
        self.assertEqual(len(matrix), 24)
        self.assertEqual(
            matrix["longs-and-jobs.md"],
            [
                "long-operation-with-result",
                "scheduled-job-module-suffix",
                "nonexistent-service-module",
            ],
        )
        self.assertEqual(unscoped, ["plain-bsl-no-bsp"])

    def test_reference_matrix_rejects_missing_reference_and_unassigned_case(self):
        cases = runner.load_cases(REPO_ROOT / "evals" / "cases.json")
        references, unscoped = runner.load_reference_matrix(
            REPO_ROOT / "evals" / "reference-matrix.json"
        )
        references.pop("admin-tools.md")
        with self.assertRaisesRegex(runner.EvalError, "matrix is missing"):
            runner.validate_reference_matrix(
                cases, references, unscoped, SKILL_DIR / "references"
            )

        references["admin-tools.md"] = []
        references["base-common.md"].remove("message-bound-to-field")
        with self.assertRaisesRegex(runner.EvalError, "does not assign"):
            runner.validate_reference_matrix(
                cases, references, unscoped, SKILL_DIR / "references"
            )

    def test_duplicate_case_id_is_rejected(self):
        payload = {
            "version": 1,
            "cases": [self._raw_case("same"), self._raw_case("same")],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(runner.EvalError, "Duplicate"):
                runner.load_cases(path)

    @staticmethod
    def _raw_case(case_id):
        return {
            "id": case_id,
            "task": "Задача",
            "required_patterns": ["Ожидается"],
            "forbidden_patterns": [],
        }


class JsonlTests(unittest.TestCase):
    def test_proxy_noise_is_ignored_and_final_message_is_extracted(self):
        text = "\n".join([
            "Запуск Codex с прокси",
            '{"type":"thread.started","thread_id":"1"}',
            '{"type":"item.completed","item":{"type":"agent_message","text":"Ответ"}}',
            '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}',
        ])
        events, noise = runner.extract_jsonl(text)
        self.assertEqual(noise, ["Запуск Codex с прокси"])
        self.assertEqual(runner.final_message(events), "Ответ")
        self.assertEqual(runner.usage_from_events(events)["input_tokens"], 10)

    def test_skill_activation_uses_observable_staged_skill_read(self):
        events = [{
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "Get-Content C:\\repo\\.agents\\skills\\bsp\\SKILL.md",
            },
        }]
        evidence = runner.skill_activation_evidence(events, "bsp")
        self.assertEqual(len(evidence), 1)

    def test_correct_answer_alone_is_not_activation(self):
        events = [{
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "БСП и правильный метод"},
        }]
        self.assertEqual(runner.skill_activation_evidence(events, "bsp"), [])


class CdxCommandTests(unittest.TestCase):
    def setUp(self):
        self.case = runner.EvalCase(
            id="test",
            task="Задача",
            reference=None,
            should_trigger=True,
            requires_bsl=False,
            required_patterns=(),
            forbidden_patterns=(),
            activation_patterns=(),
        )

    def test_windows_enables_sandbox_when_user_config_is_ignored(self):
        command = runner.build_cdx_command(
            "cdx", self.case, Path("C:/work"), None, None, platform_name="nt"
        )
        self.assertIn("--ignore-user-config", command)
        self.assertIn('windows.sandbox="unelevated"', command)

    def test_non_windows_does_not_receive_windows_config(self):
        command = runner.build_cdx_command(
            "cdx", self.case, Path("/work"), None, None, platform_name="posix"
        )
        self.assertNotIn('windows.sandbox="unelevated"', command)

    def test_luna_is_the_default_eval_model(self):
        args = runner.build_parser().parse_args([])
        self.assertEqual(args.model, "gpt-5.6-luna")
        command = runner.build_cdx_command(
            "cdx", self.case, Path("/work"), args.model, None,
            platform_name="posix",
        )
        model_index = command.index("--model")
        self.assertEqual(command[model_index + 1], "gpt-5.6-luna")


class ResponseScoringTests(unittest.TestCase):
    def setUp(self):
        self.case = runner.EvalCase(
            id="test",
            task="test",
            reference="valid.md",
            should_trigger=True,
            requires_bsl=True,
            required_patterns=(r"ТестовыйМодуль\.СтабильныйМетод\s*\(",),
            forbidden_patterns=(r"Опечатка\s*\(",),
            activation_patterns=(),
        )
        self.method_index = runner.load_method_index(SKILL_DIR, FIXTURE_SRC)

    def test_stable_export_passes(self):
        response = "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```"
        score = runner.score_response(self.case, response, self.method_index)
        self.assertTrue(score["passed"])
        self.assertEqual(score["method_accuracy"], 1.0)

    def test_missing_export_is_a_definite_hallucination(self):
        response = "```bsl\nТестовыйМодуль.СтабильныйМетод();\nТестовыйМодуль.Опечатка();\n```"
        score = runner.score_response(self.case, response, self.method_index)
        self.assertFalse(score["passed"])
        self.assertEqual(score["invalid_methods"], ["ТестовыйМодуль.Опечатка"])

    def test_forbidden_call_in_prose_is_allowed_but_code_is_not(self):
        prose = (
            "Не вызывайте Опечатка().\n"
            "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```"
        )
        code = (
            "```bsl\nТестовыйМодуль.СтабильныйМетод();\nОпечатка();\n```"
        )
        self.assertTrue(runner.score_response(self.case, prose, self.method_index)["passed"])
        self.assertFalse(runner.score_response(self.case, code, self.method_index)["passed"])

    def test_explicit_negative_code_block_is_not_a_recommended_call(self):
        response = (
            "Правильный вариант:\n"
            "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```\n"
            "Так вызывать нельзя:\n"
            "```bsl\nТестовыйМодуль.Опечатка();\n```"
        )
        score = runner.score_response(self.case, response, self.method_index)
        self.assertTrue(score["passed"])
        self.assertEqual(score["invalid_methods"], [])

    def test_real_negative_phrasings_are_not_executable_recommendations(self):
        examples = (
            (
                "Ложный очевидный API:",
                "",
            ),
            (
                "Не существует публичного вызова вида:",
                "",
            ),
            (
                "Серверного публичного метода нет. В частности:",
                "— этот метод не запускает операцию.",
            ),
            (
                "Прямого вызова вида:",
                "в прикладном коде быть не должно.",
            ),
        )
        for prefix, suffix in examples:
            with self.subTest(prefix=prefix, suffix=suffix):
                response = (
                    "Правильный вариант:\n"
                    "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```\n\n"
                    f"{prefix}\n"
                    "```bsl\nТестовыйМодуль.СлужебныйМетод();\n```\n"
                    f"{suffix}"
                )
                score = runner.score_response(self.case, response, self.method_index)
                self.assertTrue(score["passed"])
                self.assertEqual(score["unsafe_calls"], [])

    def test_negative_context_propagates_across_or_alternatives(self):
        response = (
            "Правильный вариант:\n"
            "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```\n\n"
            "Очевидный вызов вида:\n"
            "```bsl\nТестовыйМодуль.СлужебныйМетод();\n```\n\n"
            "или\n\n"
            "```bsl\nТестовыйМодуль.СлужебныйМетод();\n```\n\n"
            "Таких публичных методов нет."
        )
        score = runner.score_response(self.case, response, self.method_index)
        self.assertTrue(score["passed"])
        self.assertEqual(score["unsafe_calls"], [])
        self.assertEqual(
            runner.executable_bsl_blocks(response),
            ["ТестовыйМодуль.СтабильныйМетод();\n"],
        )

    def test_member_call_split_across_lines_is_detected(self):
        response = "```bsl\nТестовыйМодуль\n    .СтабильныйМетод();\n```"
        score = runner.score_response(self.case, response, self.method_index)
        self.assertTrue(score["passed"])
        self.assertEqual(score["known_module_calls"], ["ТестовыйМодуль.СтабильныйМетод"])

    def test_service_export_is_unsafe(self):
        case = runner.EvalCase(
            id="service",
            task="test",
            reference=None,
            should_trigger=True,
            requires_bsl=True,
            required_patterns=(r"ТестовыйМодуль\.СлужебныйМетод\s*\(",),
            forbidden_patterns=(),
            activation_patterns=(),
        )
        response = "```bsl\nТестовыйМодуль.СлужебныйМетод();\n```"
        score = runner.score_response(case, response, self.method_index)
        self.assertFalse(score["passed"])
        self.assertEqual(score["unsafe_calls"][0]["call"], "ТестовыйМодуль.СлужебныйМетод")

    def test_negative_case_must_not_show_activation_markers(self):
        case = runner.EvalCase(
            id="negative",
            task="test",
            reference=None,
            should_trigger=False,
            requires_bsl=False,
            required_patterns=(r"Ответ",),
            forbidden_patterns=(),
            activation_patterns=(r"БСП",),
        )
        clean = runner.score_response(
            case, "Ответ", {}, skill_activated=False, require_activation=True
        )
        contaminated = runner.score_response(
            case, "Ответ по БСП", {}, skill_activated=True, require_activation=True
        )
        self.assertTrue(clean["passed"])
        self.assertFalse(contaminated["passed"])


class StagingTests(unittest.TestCase):
    def test_staging_copies_and_cleans_only_target_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / ".agents" / "skills" / "bsp"
            other = root / ".agents" / "skills" / "other" / "SKILL.md"
            other.parent.mkdir(parents=True)
            other.write_text("other", encoding="utf-8")
            with runner.staged_skill(SKILL_DIR, target):
                self.assertTrue((target / "SKILL.md").is_file())
                self.assertTrue(other.is_file())
            self.assertFalse(target.exists())
            self.assertTrue(other.is_file())

    def test_staging_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ".agents" / "skills" / "bsp"
            target.mkdir(parents=True)
            with self.assertRaisesRegex(runner.EvalError, "overwrite"):
                with runner.staged_skill(SKILL_DIR, target):
                    pass


class ExecutionStatusTests(unittest.TestCase):
    @staticmethod
    def _execution(**overrides):
        execution = {
            "returncode": 0,
            "timed_out": False,
            "tool_policy_blocked": False,
            "response": "Готово",
            "stderr_tail": "",
            "score": {"passed": True},
        }
        execution.update(overrides)
        return execution

    def test_execution_status_distinguishes_quality_infrastructure_and_incomplete(self):
        self.assertEqual(runner.execution_status(self._execution()), "completed")
        self.assertEqual(
            runner.execution_status(self._execution(score={"passed": False})),
            "quality_failed",
        )
        self.assertEqual(
            runner.execution_status(self._execution(timed_out=True)),
            "infrastructure_failed",
        )
        self.assertEqual(
            runner.execution_status(self._execution(response="")),
            "incomplete",
        )

    def test_infrastructure_reason_is_classified(self):
        examples = {
            "quota exceeded": "quota_or_rate_limit",
            "authentication required": "authentication",
            "connection reset by peer": "network",
            "model is unavailable": "model_unavailable",
        }
        for stderr, expected in examples.items():
            with self.subTest(stderr=stderr):
                execution = self._execution(returncode=1, stderr_tail=stderr)
                self.assertEqual(runner.infrastructure_reason(execution), expected)


class SummaryTests(unittest.TestCase):
    def test_policy_block_is_an_infrastructure_failure(self):
        cases = [{
            "should_trigger": True,
            "complete": False,
            "majority_passed": None,
            "majority_activated": None,
            "runs": [{
                "returncode": 0,
                "tool_policy_blocked": True,
                "usage": {},
                "score": {
                    "invalid_methods": [],
                    "unsafe_calls": [],
                    "forbidden_hits": [],
                },
            }],
        }]
        summary = runner.summarize_phase(cases)
        self.assertEqual(summary["cases"], 0)
        self.assertEqual(summary["attempted_cases"], 1)
        self.assertEqual(summary["failed_processes"], 1)
        self.assertEqual(summary["tool_policy_blocks"], 1)
        self.assertEqual(summary["infrastructure_failures"], 1)
        self.assertEqual(summary["infrastructure_reasons"], {"sandbox_policy": 1})
        self.assertEqual(summary["incomplete_runs"], 0)


class ResumeReportTests(unittest.TestCase):
    def test_resume_report_rejects_incompatible_model(self):
        report = {
            "schema_version": 2,
            "model": "old-model",
            "selected_cases": ["case-a"],
            "runs": 1,
            "phases_requested": ["red", "green"],
        }
        expected = {
            "model": "new-model",
            "selected_cases": ["case-a"],
            "runs": 1,
            "phases_requested": ["red", "green"],
        }
        with self.assertRaisesRegex(runner.EvalError, "model"):
            runner.validate_resume_report(report, expected)

    def test_atomic_report_write_replaces_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            path.write_text('{"old": true}', encoding="utf-8")
            runner.atomic_write_json(path, {"complete": False})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"complete": False})
            self.assertFalse(path.with_suffix(path.suffix + ".tmp").exists())


class ParallelExecutionTests(unittest.TestCase):
    @staticmethod
    def _case(case_id):
        return runner.EvalCase(
            id=case_id,
            task="test",
            reference=None,
            should_trigger=True,
            requires_bsl=False,
            required_patterns=(),
            forbidden_patterns=(),
            activation_patterns=(),
        )

    def test_run_matrix_is_concurrent_and_preserves_order(self):
        cases = [self._case("first"), self._case("second")]
        barrier = threading.Barrier(2)
        completed = []

        def execute(case, run_number):
            barrier.wait(timeout=2)
            return {"case": case.id, "run": run_number}

        def on_run_complete(case_index, run_index, _matrix):
            completed.append((case_index, run_index))

        matrix = runner.execute_run_matrix(
            cases, runs=2, jobs=2, execute=execute,
            on_run_complete=on_run_complete,
        )

        self.assertEqual(
            matrix,
            [
                [{"case": "first", "run": 1}, {"case": "first", "run": 2}],
                [{"case": "second", "run": 1}, {"case": "second", "run": 2}],
            ],
        )
        self.assertCountEqual(completed, [(0, 0), (0, 1), (1, 0), (1, 1)])

    def test_resume_keeps_completed_attempts_and_retries_only_retryable_slots(self):
        cases = [self._case("first")]
        completed = {"status": "completed", "marker": "keep"}
        quality_failed = {"status": "quality_failed", "marker": "keep-quality"}
        infrastructure_failed = {"status": "infrastructure_failed"}
        incomplete = {"status": "incomplete"}
        initial = runner.resume_run_matrix(
            cases,
            runs=5,
            stored={
                "first": [
                    completed,
                    infrastructure_failed,
                    quality_failed,
                    incomplete,
                ]
            },
        )
        executed = []

        def execute(case, run_number):
            executed.append((case.id, run_number))
            return {"status": "completed", "marker": "new"}

        matrix = runner.execute_run_matrix(
            cases, runs=5, jobs=1, execute=execute, initial_matrix=initial
        )

        self.assertEqual(executed, [("first", 2), ("first", 4), ("first", 5)])
        self.assertEqual(matrix[0][0]["marker"], "keep")
        self.assertEqual(matrix[0][1]["marker"], "new")
        self.assertEqual(matrix[0][2]["marker"], "keep-quality")
        self.assertEqual(matrix[0][3]["marker"], "new")
        self.assertEqual(matrix[0][4]["marker"], "new")

    def test_infrastructure_attempt_does_not_count_as_quality_result(self):
        cases = [self._case("first")]
        run = {
            "status": "infrastructure_failed",
            "score": {"passed": False},
            "skill_activated": False,
        }
        records = runner.phase_case_records(cases, [[run]], expected_runs=1)
        self.assertEqual(len(records), 1)
        self.assertFalse(records[0]["complete"])
        self.assertIsNone(records[0]["majority_passed"])

    def test_phase_records_skip_incomplete_cases(self):
        cases = [self._case("first"), self._case("second")]
        passing = {
            "score": {"passed": True},
            "skill_activated": True,
        }
        records = runner.phase_case_records(
            cases,
            [[passing, passing], [passing, None]],
            expected_runs=2,
        )
        self.assertEqual([record["id"] for record in records], ["first"])


if __name__ == "__main__":
    unittest.main()
