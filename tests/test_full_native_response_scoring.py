"""Paired regressions for two wording false negatives in frozen 23826f1 runs."""
import json
import unittest
from pathlib import Path

from ci import run_skill_evals as runner

ROOT = Path(__file__).resolve().parents[1]


class FullNativeResponseScoringTests(unittest.TestCase):
    def setUp(self):
        self.cases = {case.id: case for case in runner.load_cases(runner.DEFAULT_CASES)}
        data = json.loads((ROOT / "tests/fixtures/responses/native-full-23826f1.json").read_text(encoding="utf-8"))
        self.responses = {item["case_id"]: item["response"] for item in data["items"]}
        self.methods = {module: {method: runner.MethodInfo("ПрограммныйИнтерфейс", "")}
                        for module, method in (
                            ("ОбновлениеИнформационнойБазы", "ЗаписатьДанные"),
                            ("ПодключаемыеКоманды", "ДобавитьУсловиеВидимостиКоманды"),
                        )}

    def score(self, case_id, response, **kwargs):
        return runner.score_response(self.cases[case_id], response, self.methods,
                                     skill_activated=kwargs.get("activated", True), require_activation=True,
                                     reference_read=kwargs.get("read", True), require_reference=True)

    def test_captured_equivalent_module_rejection_and_bsp_caller_pass(self):
        for case_id, response in self.responses.items():
            with self.subTest(case_id=case_id):
                self.assertTrue(self.score(case_id, response)["passed"])

    def test_error_word_without_wrong_module_name_does_not_satisfy_rejection(self):
        case = "update-safe-write-module-name"
        for replacement in ("ошибка при записи", "ошибочное имя метода",
                            "ошибочное имя другого модуля", "правильное имя модуля",
                            "безошибочное имя модуля", "неошибочное имя модуля",
                            "не ошибочное имя модуля", "не  ошибочное имя модуля"):
            with self.subTest(replacement=replacement):
                response = self.responses[case].replace("ошибочное имя модуля", replacement)
                self.assertFalse(self.score(case, response)["passed"])

    def test_unrelated_module_rejection_does_not_satisfy_target_name_rejection(self):
        case = "update-safe-write-module-name"
        response = self.responses[case].replace("ошибочное имя модуля", "правильное имя модуля")
        response += "\nДругой пример содержит ошибочное имя модуля."
        self.assertFalse(self.score(case, response)["passed"])

    def test_new_module_wording_does_not_excuse_wrong_recommended_call(self):
        case = "update-safe-write-module-name"
        response = self.responses[case].replace(
            "ОбновлениеИнформационнойБазы.ЗаписатьДанные(ДокументОбъект);",
            "ОбновлениеИнформационнойБазыСервер.ЗаписатьДанные(ДокументОбъект);")
        self.assertFalse(self.score(case, response)["passed"])

    def test_infrastructure_without_bsp_caller_does_not_satisfy_boundary(self):
        case = "connected-command-hook-boundary"
        for caller in ("инфраструктура прикладной конфигурации", "инфраструктура теста"):
            with self.subTest(caller=caller):
                response = self.responses[case].replace("инфраструктура БСП", caller)
                self.assertFalse(self.score(case, response)["passed"])

    def test_bsp_caller_wording_does_not_excuse_direct_hook_call(self):
        case = "connected-command-hook-boundary"
        response = self.responses[case].replace(
            "КонецПроцедуры\n```",
            "КонецПроцедуры\nПодключаемыеКомандыПереопределяемый.ПриОпределенииКомандПодключенныхКОбъекту(НастройкиФормы, Источники, ПодключенныеОтчетыИОбработки, Команды);\n```")
        score = self.score(case, response)
        self.assertFalse(score["passed"])
        self.assertTrue(score["forbidden_hits"])

    def test_bsp_caller_wording_still_requires_correct_hook_skeleton(self):
        case = "connected-command-hook-boundary"
        response = self.responses[case].replace(
            "НастройкиФормы, Источники, ПодключенныеОтчетыИОбработки, Команды",
            "Команды, Источник")
        score = self.score(case, response)
        self.assertFalse(score["passed"])
        self.assertTrue(score["missing_code_patterns"])

    def test_correct_wording_still_requires_activation_and_reference_read(self):
        for case_id, response in self.responses.items():
            with self.subTest(case_id=case_id):
                self.assertFalse(self.score(case_id, response, activated=False)["passed"])
                self.assertFalse(self.score(case_id, response, read=False)["passed"])


if __name__ == "__main__":
    unittest.main()
