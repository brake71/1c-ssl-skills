#!/usr/bin/env python3
"""Check four high-risk BSL examples in BSP references (not a BSL compiler).

Only fenced code inside the selected scenario is checked. These contracts catch
specific regressions that API-claim validation cannot see in runnable examples.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "skills" / "bsp" / "references"
FENCE = re.compile(r"(?m)^```bsl\s*\n(.*?)^```\s*$", re.S)


@dataclass(frozen=True)
class Contract:
    file: str
    heading: str
    anchor: str
    required: tuple[str, ...]
    forbidden: tuple[str, ...]


CONTRACTS = (
    Contract(
        "users-access.md", "### 3. Проверить RLS-доступ", "**Пример отказа без исключения",
        (r"Если\s+Не\s+УправлениеДоступом\.ЧтениеРазрешено\s*\(\s*Объект\.ДокументОснование\s*\)\s*Тогда"
         r"(?:(?!КонецЕсли).)*ОбщегоНазначения\.СообщитьПользователю\s*\([^;]*?,\s*,\s*"
         r'"Объект\.ДокументОснование"\s*,\s*,\s*Отказ\s*\)\s*;(?:(?!КонецЕсли).)*КонецЕсли\s*;',),
        (r"УправлениеДоступом\.ПроверитьЧтениеРазрешено\s*\(",
         r"УстановитьПривилегированныйРежим\s*\("),
    ),
    Contract(
        "update.md", "### 2. Безопасно записать данные", "**Пример:**",
        (r"ОбновлениеИнформационнойБазы\.ЗаписатьДанные\s*\(\s*ДокументОбъект\s*\)",),
        (r"ДокументОбъект\.Записать\s*\(",
         r"ОбновлениеИнформационнойБазыСервер\.ЗаписатьДанные\s*\("),
    ),
    Contract(
        "files-and-versions.md", "### 1. Прикрепить файл", "**Пример:**",
        (r"ПараметрыФайла\s*=\s*РаботаСФайлами\.ПараметрыДобавленияФайла\s*\(\s*\)",
         r"ПараметрыФайла\.ВладелецФайлов\s*=\s*ЗаказПоставщику\s*;"
         r".*?РаботаСФайлами\.ДобавитьФайл\s*\(\s*ПараметрыФайла\s*,\s*АдресДвоичныхДанныхВХ\s*,"),
        (r"РаботаСФайламиСлужебный\.ДобавитьФайл\s*\(",),
    ),
    Contract(
        "longs-and-jobs.md", "### 3. Показать прогресс", "**Пример:**",
        (r"Процедура\s+ОбработатьНаборДанных\s*\([^)]*\)\s*Экспорт"
         r"(?:(?!КонецПроцедуры).)*ДлительныеОперации\.СообщитьПрогресс\s*\(",
         r"&НаКлиенте\s+Процедура\s+Запустить\s*\([^)]*\)"
         r"(?:(?!КонецПроцедуры).)*ДлительныеОперацииКлиент\.ПараметрыОжидания\s*\("
         r"(?:(?!КонецПроцедуры).)*ВыводитьПрогрессВыполнения\s*=\s*Истина\s*;"
         r"(?:(?!КонецПроцедуры).)*ДлительныеОперацииКлиент\.ОжидатьЗавершение\s*\("
         r"[^;]*?,\s*ПараметрыОжидания\s*\)"),
        (r"ДлительныеОперацииКлиент\.СообщитьПрогресс\s*\(",),
    ),
)


def example_code(markdown: str, contract: Contract) -> str:
    headings = list(re.finditer(r"(?m)^###\s+.*$", markdown))
    matching = [i for i, match in enumerate(headings)
                if match.group().startswith(contract.heading)]
    if len(matching) != 1:
        raise ValueError(f"expected one scenario heading {contract.heading!r}")
    index = matching[0]
    section = markdown[headings[index].end():headings[index + 1].start()
                       if index + 1 < len(headings) else len(markdown)]
    if section.count(contract.anchor) != 1:
        raise ValueError(f"expected one example marker {contract.anchor!r}")
    fences = list(FENCE.finditer(section, section.index(contract.anchor) + len(contract.anchor)))
    if not fences:
        raise ValueError("missing fenced BSL example after marker")
    return fences[0].group(1)


def check_code(code: str, contract: Contract) -> list[str]:
    # Only this narrow check strips comments; string literals are not parsed.
    executable = re.sub(r"//[^\n]*", "", code)
    errors = []
    for pattern in contract.required:
        if not re.search(pattern, executable, re.S | re.I):
            errors.append(f"missing required code: {pattern}")
    for pattern in contract.forbidden:
        if re.search(pattern, executable, re.S | re.I):
            errors.append(f"forbidden code: {pattern}")
    return errors


def validate(root: Path) -> list[str]:
    errors = []
    for contract in CONTRACTS:
        try:
            code = example_code((root / contract.file).read_text(encoding="utf-8"), contract)
        except (OSError, ValueError) as exc:
            errors.append(f"{contract.file}: {exc}")
            continue
        errors.extend(f"{contract.file}: {error}" for error in check_code(code, contract))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references-root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.references_root)
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print(f"OK: {len(CONTRACTS)} critical BSL examples match their contracts (not compiled)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
