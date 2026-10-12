"""Keep the access-right hook example aligned with its documented table contract."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AccessHookExampleTests(unittest.TestCase):
    def test_access_right_hook_uses_real_name_and_table_columns(self):
        reference = (ROOT / "skills/bsp/references/users-access.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```bsl\n(.*?)```", reference, re.S)
        examples = [code for code in blocks if "ВозможныеПрава" in code]
        self.assertEqual(len(examples), 1)
        code = examples[0]
        self.assertIn(
            "Процедура ПриЗаполненииВозможныхПравДляНастройкиПравОбъектов(ВозможныеПрава) Экспорт",
            code,
        )
        self.assertIn("Право = ВозможныеПрава.Добавить();", code)
        self.assertIn("Право.ВладелецПрав =", code)
        self.assertIn("Право.Заголовок =", code)
        for field in ("ТребуемыеПрава", "ЧтениеВТаблицах", "ИзменениеВТаблицах"):
            with self.subTest(field=field):
                self.assertIn(f"Право.{field} = Новый Массив;", code)
        self.assertNotIn("ВозможныеПрава.Строки", code)
        self.assertNotIn("Право.Описание", code)
        self.assertNotIn("ПриЗаполнение", reference)
        self.assertIn("обязательное\n`УправлениеПравами`", reference)


if __name__ == "__main__":
    unittest.main()
