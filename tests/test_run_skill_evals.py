import importlib.util
import json
import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main()
