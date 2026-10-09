"""Paired semantic controls for the captured a728b0b smoke wording refusal."""
import unittest
from pathlib import Path

from ci import run_skill_evals as runner

ROOT = Path(__file__).resolve().parents[1]
WARNING = ("Путь идентифицирует данные для привязки самостоятельно; вместе с ключом он задаёт "
           "конкурирующий способ адресации, поэтому эти варианты не совмещают.")


class MessageBindingScoringTests(unittest.TestCase):
    def setUp(self):
        self.case = next(c for c in runner.load_cases(runner.DEFAULT_CASES) if c.id == "message-bound-to-field")
        self.response = (ROOT / "tests/fixtures/responses/native-message-binding-a728b0b.md").read_text(encoding="utf-8").strip()
        # Real signature/contract verified in BSP 3.1.11 docs and read-only src/cf.
        self.methods = {"ОбщегоНазначения": {"СообщитьПользователю": runner.MethodInfo("ПрограммныйИнтерфейс", "")}}

    def score(self, response):
        return runner.score_response(self.case, response, self.methods,
                                     skill_activated=True, require_activation=True,
                                     reference_read=True, require_reference=True)

    def test_captured_non_combination_explanation_passes(self):
        self.assertTrue(self.score(self.response)["passed"])

    def test_entity_pair_and_actual_prohibition_are_required(self):
        for replacement in (
            WARNING.replace("Путь идентифицирует", "Способ идентифицирует"),
            WARNING.replace("с ключом", "с объектом"),
            WARNING.replace("не совмещают", "можно совмещать"),
            WARNING.replace("не совмещают", "совмещают"),
            WARNING.replace("не совмещают", "не не совмещают"),
            "Путь к файлу и ключ шифрования верны. Эти варианты не совмещают.",
        ):
            with self.subTest(replacement=replacement):
                self.assertFalse(self.score(self.response.replace(WARNING, replacement))["passed"])

    def test_unrelated_non_combination_sentence_does_not_satisfy_boundary(self):
        response = self.response.replace(WARNING, "Два способа адресации описаны выше.")
        response += "\nЭти варианты настройки Отказ не совмещают."
        self.assertFalse(self.score(response)["passed"])

    def test_valid_explanation_does_not_hide_an_invalid_runnable_api(self):
        response = self.response.replace("Отказ);", "Отказ);\n    ОбщегоНазначения.Опечатка();")
        score = self.score(response)
        self.assertFalse(score["passed"])
        self.assertEqual(score["invalid_methods"], ["ОбщегоНазначения.Опечатка"])

    def test_valid_explanation_does_not_hide_forbidden_platform_object(self):
        response = self.response.replace("Отказ);", "Отказ);\n    Сообщение = Новый СообщениеПользователю;")
        score = self.score(response)
        self.assertFalse(score["passed"])
        self.assertTrue(score["forbidden_hits"])


if __name__ == "__main__":
    unittest.main()
