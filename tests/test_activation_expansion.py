"""Paired controls for guidance-free navigation, RLS, printing and a two-topic task."""
import unittest
from dataclasses import replace
from pathlib import Path

from ci import run_skill_evals as runner

ROOT = Path(__file__).resolve().parents[1]
ANSWERS = {
    "neutral-public-api-boundary": (
        "ВызовСервера: код исполняется на сервере, вызов инициирует клиент. "
        "Экспорт не означает стабильность. СлужебныйПрограммныйИнтерфейс — "
        "совместимость не гарантируется; выбирайте ПрограммныйИнтерфейс "
        "и проверяйте назначение и свойства общего модуля."
    ),
    "neutral-rls-read-guard": (
        "Серверная проверка выбрасывает исключение при запрете:\n"
        "```bsl\nУправлениеДоступом.ПроверитьЧтениеРазрешено(СсылкаНаДокумент);\n```"
    ),
    "neutral-print-registration": '''БСП вызывает обработчики. Регистрация в УправлениеПечатьюПереопределяемый:
```bsl
Процедура ПриОпределенииНастроекПечати(Настройки) Экспорт
    Настройки.ОбъектыПечати.Добавить(Документы.Счет);
КонецПроцедуры
```
Модуль менеджера документа Счет:
```bsl
Процедура ПриОпределенииНастроекПечати(Настройки) Экспорт
    Настройки.ПриДобавленииКомандПечати = Истина;
КонецПроцедуры
Процедура ДобавитьКомандыПечати(КомандыПечати) Экспорт
    Команда = КомандыПечати.Добавить();
    Команда.Идентификатор = "Счет";
    Команда.Представление = "Счет";
КонецПроцедуры
```''',
    "neutral-rls-field-message": '''Серверный обработчик:
```bsl
Если Не УправлениеДоступом.ЧтениеРазрешено(Объект.ДокументОснование) Тогда
    Отказ = Истина;
    ОбщегоНазначения.СообщитьПользователю(
        "Чтение документа запрещено", , "Объект.ДокументОснование");
КонецЕсли;
```''',
}


class ActivationExpansionTests(unittest.TestCase):
    def setUp(self):
        self.cases = {case.id: case for case in runner.load_cases(ROOT / "evals/activation-cases.json")}
        self.methods = {
            "УправлениеДоступом": {
                name: runner.MethodInfo("ПрограммныйИнтерфейс", "")
                for name in ("ЧтениеРазрешено", "ПроверитьЧтениеРазрешено")
            },
            "ОбщегоНазначения": {
                "СообщитьПользователю": runner.MethodInfo("ПрограммныйИнтерфейс", "")
            },
            "УправлениеПечатьюПереопределяемый": {
                "ПриОпределенииНастроекПечати": runner.MethodInfo("ПрограммныйИнтерфейс", "")
            },
        }

    def score(self, case_id, response, *, activated=True, read=True):
        return runner.score_response(
            self.cases[case_id], response, self.methods, skill_activated=activated,
            require_activation=True, reference_read=read, require_reference=True,
        )

    def test_positive_controls_and_required_evidence(self):
        for case_id, response in ANSWERS.items():
            with self.subTest(case=case_id):
                self.assertTrue(self.score(case_id, response)["passed"])
                self.assertFalse(self.score(case_id, response, activated=False)["passed"])
                self.assertFalse(self.score(case_id, response, read=False)["passed"])

    def test_prompts_do_not_reveal_skill_paths_or_reference_selection(self):
        for case_id in ANSWERS:
            task = self.cases[case_id].task
            with self.subTest(case=case_id):
                self.assertNotIn("БСП 3.1.11", task)
                for hint in ("SKILL.md", ".agents/", "references/", "прочитай скил"):
                    self.assertNotIn(hint, task)

    def test_navigation_does_not_accept_promised_internal_compatibility(self):
        case = "neutral-public-api-boundary"
        wrong = ANSWERS[case].replace("не означает стабильность", "означает стабильность").replace(
            "не гарантируется", "гарантируется"
        )
        self.assertFalse(self.score(case, wrong)["passed"])
        self.assertFalse(self.score(case, ANSWERS[case].replace("на сервере", "на клиенте"))["passed"])

    def test_rls_guard_requires_executable_public_exception_check(self):
        case = "neutral-rls-read-guard"
        response = ANSWERS[case]
        for wrong in (
            response.replace("ПроверитьЧтениеРазрешено", "ЧтениеРазрешено"),
            response.replace("СсылкаНаДокумент", "Метаданные.Документы.Счет"),
            response.replace("УправлениеДоступом.", "УправлениеДоступомСлужебный."),
            response.replace("```bsl\n", "```bsl\n// "),
            response.replace("```bsl\n", "```bsl\nУстановитьПривилегированныйРежим(Истина);\n"),
        ):
            with self.subTest(wrong=wrong):
                self.assertFalse(self.score(case, wrong)["passed"])

    def test_printing_requires_registration_flag_and_one_argument_hook(self):
        case = "neutral-print-registration"
        response = ANSWERS[case]
        for before, after in (
            ("Настройки.ОбъектыПечати.Добавить(Документы.Счет);", ""),
            ("Настройки.ПриДобавленииКомандПечати = Истина;", ""),
            ("ПриДобавленииКомандПечати = Истина", "ПриДобавленииКомандПечати = Ложь"),
            ("ДобавитьКомандыПечати(КомандыПечати)", "ДобавитьКомандыПечати(КомандыПечати, Параметры)"),
            ('Идентификатор = "Счет"', 'Идентификатор = "Акт"'),
        ):
            with self.subTest(before=before):
                self.assertFalse(self.score(case, response.replace(before, after))["passed"])
        self.assertFalse(self.score(case, response + (
            "\n```bsl\nУправлениеПечатьюПереопределяемый."
            "ПриОпределенииНастроекПечати(Настройки);\n```"
        ))["passed"])
        self.assertFalse(self.score(case, response.replace(
            "Команда = КомандыПечати.Добавить();",
            "КомандыПечати = УправлениеПечатью.СоздатьКоллекциюКомандПечати();\n"
            "Команда = КомандыПечати.Добавить();"
        ))["passed"])

    def test_two_topic_refusal_requires_rls_field_binding_and_refusal_effect(self):
        case = "neutral-rls-field-message"
        response = ANSWERS[case]
        for before, after in (
            ("ЧтениеРазрешено", "ПроверитьЧтениеРазрешено"),
            ("Если Не УправлениеДоступом", "Если УправлениеДоступом"),
            ('"Объект.ДокументОснование"', '"Объект.Организация"'),
            ("Отказ = Истина;", "Отказ = Ложь;"),
            ("Отказ = Истина;", 'ВызватьИсключение "Нет доступа";'),
            ("ОбщегоНазначения.СообщитьПользователю", "Сообщить"),
        ):
            with self.subTest(before=before):
                self.assertFalse(self.score(case, response.replace(before, after))["passed"])

    def test_captured_incomplete_print_registration_stays_fail(self):
        response = (ROOT / "tests/fixtures/responses/v016-incomplete-print-registration.md").read_text(encoding="utf-8")
        score = self.score("neutral-print-registration", response)
        self.assertFalse(score["passed"])
        self.assertTrue(score["missing_code_patterns"])

    def test_refusal_must_be_inside_the_rls_denial_branch(self):
        case = "neutral-rls-field-message"
        without_refusal = ANSWERS[case].replace("    Отказ = Истина;\n", "")
        outside_after = without_refusal.replace("КонецЕсли;", "КонецЕсли;\nОтказ = Истина;")
        outside_before = without_refusal.replace("```bsl\n", "```bsl\nОтказ = Истина;\n")
        literal_refusal = outside_after.replace(
            '"Чтение документа запрещено"', '"Отказ = Истина"'
        )
        for response in (outside_after, outside_before, literal_refusal):
            with self.subTest(response=response):
                self.assertFalse(self.score(case, response)["passed"])

    def test_denied_read_description_is_not_a_prohibition_of_the_public_call(self):
        case = "neutral-rls-field-message"
        code = ANSWERS[case].replace("Серверный обработчик:\n", "")
        response = (
            "УправлениеДоступом.ЧтениеРазрешено() возвращает Ложь, "
            "если чтение запрещено. Для сообщения используйте "
            "ОбщегоНазначения.СообщитьПользователю():\n\n" + code
        )
        self.assertTrue(self.score(case, response)["passed"])
        for warning in (
            "УправлениеДоступом.ЧтениеРазрешено() вызывать запрещено. ",
            "УправлениеДоступом.ЧтениеРазрешено() возвращает Ложь, "
            "если чтение запрещено; этот вызов использовать нельзя. ",
        ):
            with self.subTest(warning=warning):
                self.assertFalse(self.score(case, warning + "\n\n" + code)["passed"])

    def test_checked_reference_is_not_the_key_of_the_form_field_message(self):
        case = "neutral-rls-field-message"
        response = (ROOT / "tests/fixtures/responses/v016-rls-wrong-message-key.md").read_text(encoding="utf-8")
        score = self.score(case, response)
        self.assertFalse(score["passed"])
        self.assertIn("УправлениеДоступом.ЧтениеРазрешено", score["known_module_calls"])
        self.assertIn("ОбщегоНазначения.СообщитьПользователю", score["known_module_calls"])
        correct_binding = response.replace("        Объект.ДокументОснование,\n", "        ,\n")
        self.assertTrue(self.score(case, correct_binding)["passed"])

    def test_dead_nested_branch_cannot_supply_denial_effects(self):
        case = "neutral-rls-field-message"
        response = ANSWERS[case].replace(
            "    Отказ = Истина;", "    Если Ложь Тогда\n        Отказ = Истина;"
        ).replace("КонецЕсли;", "    КонецЕсли;\nКонецЕсли;")
        self.assertFalse(self.score(case, response)["passed"])

    def test_one_if_scope_rejects_extra_conditions(self):
        case = "neutral-rls-field-message"
        response = ANSWERS[case]
        outer_condition = response.replace(
            "```bsl\n", "```bsl\nЕсли Ложь Тогда\n"
        ).replace("КонецЕсли;", "КонецЕсли;\nКонецЕсли;")
        nested_condition = response.replace(
            "    Отказ = Истина;", "    Если Истина Тогда\n        Отказ = Истина;"
        ).replace("КонецЕсли;", "    КонецЕсли;\nКонецЕсли;")
        else_if_condition = response.replace(
            "Если Не УправлениеДоступом", "Если УправлениеДоступом"
        ).replace(" Тогда\n", " Тогда\nИначеЕсли Ложь Тогда\n")
        for code in (outer_condition, nested_condition, else_if_condition):
            with self.subTest(code=code):
                self.assertFalse(self.score(case, code)["passed"])

    def test_one_if_scope_ignores_keyword_literals_and_accepts_procedure_wrapper(self):
        case = "neutral-rls-field-message"
        response = ANSWERS[case].replace(
            "```bsl\n", "```bsl\nПроцедура ПроверкаЗаписи(Отказ)\n"
        ).replace(
            "    Отказ = Истина;", "    // Если ИначеЕсли Если\n    Отказ = Истина;"
        ).replace(
            '"Чтение документа запрещено"', '"Чтение запрещено: Если ИначеЕсли Если"'
        ).replace("КонецЕсли;", "КонецЕсли;\nКонецПроцедуры")
        self.assertTrue(self.score(case, response)["passed"])

    def test_message_must_be_in_the_same_denial_branch_as_refusal(self):
        response = ANSWERS["neutral-rls-field-message"].replace(
            "    ОбщегоНазначения.СообщитьПользователю(",
            "Иначе\n    ОбщегоНазначения.СообщитьПользователю("
        )
        self.assertFalse(self.score("neutral-rls-field-message", response)["passed"])

    def test_syntax_patterns_mask_comments_and_literal_effects(self):
        pattern = r"Отказ\s*=\s*Истина"
        case = replace(
            self.cases["neutral-rls-field-message"], required_patterns=("Готово",),
            required_code_patterns=(), required_syntax_patterns=(pattern,),
            forbidden_code_patterns=(),
        )
        for code in ('Сообщить("Отказ = Истина");', '// Отказ = Истина;\nСообщить("Готово");'):
            with self.subTest(code=code):
                score = runner.score_response(case, f"Готово\n```bsl\n{code}\n```", {})
                self.assertFalse(score["quality_passed"])
                self.assertEqual(score["missing_syntax_patterns"], [pattern])
        score = runner.score_response(case, 'Готово\n```bsl\nОтказ = Истина;\n```', {})
        self.assertTrue(score["quality_passed"])
        self.assertEqual(score["expected_hits"], score["expected_total"])
        self.assertEqual(score["expected_score"], 1.0)

    def test_field_message_accepts_key_object_and_refusal_argument(self):
        case = "neutral-rls-field-message"
        response = ANSWERS[case].replace("    Отказ = Истина;\n", "").replace(
            '"Чтение документа запрещено", , "Объект.ДокументОснование");',
            '"Чтение документа запрещено", Объект, "ДокументОснование", , Отказ);'
        )
        self.assertTrue(self.score(case, response)["passed"])
        path_binding = response.replace(
            '"Чтение документа запрещено", Объект, "ДокументОснование", , Отказ);',
            '"Чтение документа запрещено", , "ДокументОснование", "Объект", Отказ);'
        )
        self.assertTrue(self.score(case, path_binding)["passed"])
        positive_branch = ANSWERS[case].replace(
            "Если Не УправлениеДоступом", "Если УправлениеДоступом"
        ).replace(" Тогда\n", " Тогда\n    // Доступ разрешён.\nИначе\n")
        self.assertTrue(self.score(case, positive_branch)["passed"])


if __name__ == "__main__":
    unittest.main()
