"""Positive and adversarial controls for high-risk BSL reference examples."""
import tempfile
import unittest
from pathlib import Path

from ci import check_critical_examples as examples


class CriticalExamplesTests(unittest.TestCase):
    def setUp(self):
        self.contracts = {contract.file: contract for contract in examples.CONTRACTS}

    def code(self, file):
        contract = self.contracts[file]
        return examples.example_code((examples.ROOT / file).read_text(encoding="utf-8"), contract)

    def test_current_examples_pass(self):
        self.assertEqual(examples.validate(examples.ROOT), [])
        for file, contract in self.contracts.items():
            with self.subTest(file=file):
                self.assertEqual(examples.check_code(self.code(file), contract), [])

    def test_rls_rejects_hard_check_missing_field_and_missing_refusal(self):
        file = "users-access.md"
        code, contract = self.code(file), self.contracts[file]
        for before, after in (
            ("УправлениеДоступом.ЧтениеРазрешено", "УправлениеДоступом.ПроверитьЧтениеРазрешено"),
            ('"Объект.ДокументОснование"', '"ДокументОснование"'),
            (", , Отказ);", ", , Ложь);"),
        ):
            with self.subTest(replacement=after):
                self.assertIn(before, code)
                self.assertTrue(examples.check_code(code.replace(before, after), contract))

    def test_update_rejects_direct_write_and_wrong_module(self):
        file = "update.md"
        code, contract = self.code(file), self.contracts[file]
        for replacement in ("ДокументОбъект.Записать()",
                            "ОбновлениеИнформационнойБазыСервер.ЗаписатьДанные(ДокументОбъект)"):
            with self.subTest(replacement=replacement):
                self.assertTrue(examples.check_code(
                    code.replace("ОбновлениеИнформационнойБазы.ЗаписатьДанные(ДокументОбъект)",
                                 replacement), contract))

    def test_file_example_requires_owner_and_parameter_order(self):
        file = "files-and-versions.md"
        code, contract = self.code(file), self.contracts[file]
        for before, after in (
            ("ПараметрыФайла.ВладелецФайлов      = ЗаказПоставщику;", ""),
            ("    ПараметрыФайла,\n    АдресДвоичныхДанныхВХ,",
             "    ЗаказПоставщику,\n    АдресДвоичныхДанныхВХ,"),
        ):
            with self.subTest(replacement=after):
                self.assertIn(before, code)
                self.assertTrue(examples.check_code(code.replace(before, after), contract))

    def test_progress_requires_client_context_and_flag(self):
        file = "longs-and-jobs.md"
        code, contract = self.code(file), self.contracts[file]
        for before, after in (
            ("&НаКлиенте", ""),
            ("ВыводитьПрогрессВыполнения = Истина", "ВыводитьПрогрессВыполнения = Ложь"),
            ("ДлительныеОперации.СообщитьПрогресс", "ДлительныеОперацииКлиент.СообщитьПрогресс"),
        ):
            with self.subTest(replacement=after):
                self.assertIn(before, code)
                self.assertTrue(examples.check_code(code.replace(before, after), contract))

    def test_prose_and_comments_cannot_satisfy_contract(self):
        file = "update.md"
        contract = self.contracts[file]
        code = "// ОбновлениеИнформационнойБазы.ЗаписатьДанные(ДокументОбъект);\nДокументОбъект.Записать();"
        self.assertTrue(examples.check_code(code, contract))

    def test_missing_or_moved_example_fails_closed(self):
        file = "users-access.md"
        contract = self.contracts[file]
        text = (examples.ROOT / file).read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            examples.example_code(text.replace(contract.anchor, "**Другое название", 1), contract)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in self.contracts:
                (root / name).write_text((examples.ROOT / name).read_text(encoding="utf-8"),
                                         encoding="utf-8")
            (root / file).write_text(text.replace(contract.anchor, "**Другое название", 1),
                                     encoding="utf-8")
            self.assertTrue(examples.validate(root))


if __name__ == "__main__":
    unittest.main()
