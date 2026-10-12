"""Paired controls for the captured key/path ambiguity warning."""
import unittest
from pathlib import Path

from ci import run_skill_evals as runner

ROOT = Path(__file__).resolve().parents[1]


class MessageWarningWordingTests(unittest.TestCase):
    def setUp(self):
        self.case = next(case for case in runner.load_cases(ROOT / "evals/cases.json")
                         if case.id == "message-bound-to-field")
        self.response = (ROOT / "tests/fixtures/responses/v016-message-warning-wording.md").read_text(encoding="utf-8")
        self.methods = {"ОбщегоНазначения": {
            "СообщитьПользователю": runner.MethodInfo("ПрограммныйИнтерфейс", ""),
        }}

    def score(self, response, *, activated=True, read=True):
        return runner.score_response(
            self.case, response, self.methods, skill_activated=activated,
            require_activation=True, reference_read=read, require_reference=True,
        )

    def test_captured_ambiguity_warning_is_an_equivalent_explanation(self):
        self.assertTrue(self.score(self.response)["passed"])
        self.assertFalse(self.score(self.response, activated=False)["passed"])
        self.assertFalse(self.score(self.response, read=False)["passed"])

    def test_simultaneous_transfer_without_rejection_is_not_a_warning(self):
        response = self.response.replace(
            "Одновременная передача ключа и пути создаёт неоднозначность привязки, поэтому выбирают один способ.",
            "Одновременная передача ключа и пути разрешена, поэтому используют оба способа.",
        )
        self.assertNotEqual(response, self.response)
        self.assertFalse(self.score(response)["passed"])
        missing = self.response.replace(
            "Одновременная передача ключа и пути создаёт неоднозначность привязки, поэтому выбирают один способ.", ""
        )
        self.assertFalse(self.score(missing)["passed"])
        negated_choice = self.response.replace("поэтому выбирают один способ", "поэтому не выбирают один способ")
        self.assertFalse(self.score(negated_choice)["passed"])

    def test_equivalent_warning_does_not_excuse_a_nonexistent_call(self):
        response = self.response.replace("ОбщегоНазначения.СообщитьПользователю", "ОбщегоНазначения.НеСуществует")
        score = self.score(response)
        self.assertFalse(score["passed"])
        self.assertIn("ОбщегоНазначения.НеСуществует", score["invalid_methods"])


if __name__ == "__main__":
    unittest.main()
