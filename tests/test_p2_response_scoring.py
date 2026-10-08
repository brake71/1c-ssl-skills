"""Replay regressions for false negatives found in the native guided baseline."""
import json
import unittest
from pathlib import Path

from ci import run_skill_evals as runner

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/responses/native-guided-p2.json"


class P2ResponseScoringTests(unittest.TestCase):
    def setUp(self):
        self.cases = {case.id: case for case in runner.load_cases(runner.DEFAULT_CASES)}
        self.responses = {item["case_id"]: item["response"] for item in
                          json.loads(FIXTURE.read_text(encoding="utf-8"))["items"]}
        # Portable signature inventory; actual signatures/regions independently
        # checked against BSP 3.1.11 documentation and src/cf during diagnosis.
        self.methods = {module: {method: runner.MethodInfo("ПрограммныйИнтерфейс", "")}
                        for module, method in (
                            ("РегламентныеЗаданияСервер", "ДобавитьЗадание"),
                            ("ДлительныеОперации", "СообщитьПрогресс"),
                            ("ОтправкаSMS", "ОтправитьSMS"),
                            ("ПодключаемыеКоманды", "ДобавитьУсловиеВидимостиКоманды"),
                        )}

    def score(self, case_id, response):
        return runner.score_response(self.cases[case_id], response, self.methods,
                                     skill_activated=True, require_activation=True,
                                     reference_read=True, require_reference=True)

    def test_captured_correct_responses_pass_without_changing_thresholds(self):
        for case_id, response in self.responses.items():
            with self.subTest(case_id=case_id):
                self.assertTrue(self.score(case_id, response)["passed"])
                self.assertEqual(len(runner.executable_bsl_blocks(response)), 1)

    def test_wrong_call_remains_visible_beside_ancillary_argument_warning(self):
        case_id = "sms-public-wrapper-not-hook"
        response = self.responses[case_id].replace(
            "Результат = ОтправкаSMS.ОтправитьSMS(НомераПолучателей, Текст);",
            "Результат = ОтправкаSMS.ОтправитьSMS(НомераПолучателей, Текст);\n"
            "    ОтправкаSMS.Опечатка();")
        score = self.score(case_id, response)
        self.assertEqual(score["invalid_methods"], ["ОтправкаSMS.Опечатка"])
        self.assertFalse(score["passed"])

    def test_nearest_sentence_labels_example_but_explicit_warning_still_applies(self):
        block = "```bsl\nДлительныеОперации.СообщитьПрогресс(50);\n```"
        positive = ("Другого публичного метода нет. Используйте стабильный API. Например:\n" + block)
        self.assertEqual(len(runner.executable_bsl_blocks(positive)), 1)
        for label in ("Публичного метода нет. Например:", "Так делать нельзя. Например:",
                      "ДлительныеОперации.СообщитьПрогресс вызывать нельзя. Например:"):
            with self.subTest(label=label):
                self.assertEqual(runner.executable_bsl_blocks(label + "\n" + block), [])

    def test_argument_warning_cannot_override_direct_call_prohibition(self):
        block = "```bsl\nОтправкаSMS.ОтправитьSMS(НомераПолучателей, Текст);\n```"
        for note in ("Этот вызов не следует использовать; логин в этот вызов передавать не нужно.",
                     "Этот метод не следует вызывать; пароль в этот метод передавать не нужно."):
            with self.subTest(note=note):
                self.assertEqual(runner.executable_bsl_blocks(block + "\n\n" + note), [])

    def test_text_assertions_still_require_rejection_and_hook_boundary(self):
        progress = self.responses["nonexistent-service-module"].replace(
            "Совет почти верный по смыслу, но имя модуля указано неправильно.", "Совет правильный.")
        self.assertFalse(self.score("nonexistent-service-module", progress)["passed"])
        hook = self.responses["connected-command-hook-boundary"]
        hook = hook[:hook.index("`ПриОпределенииКомандПодключенныхКОбъекту` — хук")]
        self.assertFalse(self.score("connected-command-hook-boundary", hook)["passed"])


if __name__ == "__main__":
    unittest.main()
