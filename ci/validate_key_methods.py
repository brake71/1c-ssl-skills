#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI validator: check `Module.Method` mentions against actual BSP source code.

For every `Module.Method` mention found in the BSP skill's reference files
(`.claude/skills/bsp/references/*.md`), the validator:
  1. Extracts the `Module.Method` token from backticked code spans, plus any
     declared stability (markers "стабильный"/"служебный" in the row), if present.
  2. Parses the real `.bsl` module from the configuration export (`--src`)
     with the BSP skill's own parser (bsp_api.parse_export_methods).
  3. Reports mismatches:
     - module not found in the export (typos, hallucinated module names)
     - method not exported from the module (typos, hallucinated method names)
     - method declared "стабильный" while actually in a non-stable region
       (`СлужебныйПрограммныйИнтерфейс` / `СлужебныеПроцедурыИФункции`, etc.)
     - method declared "служебный" while actually in `ПрограммныйИнтерфейс`
       (over-conservative, less severe)

Note: the new unified `bsp/` skill carries full inline signatures in workflow
scenarios rather than a dedicated "Стабильность" table column, so most mentions
have no declared stability — the validator then only confirms existence of the
module/method (the main guard against hallucinated names).

Exit code 0 = all checks pass; 1 = mismatches found; 2 = bad --src / --skills-dir.

Usage:
    python ci/validate_key_methods.py --src <path/to/cf>
    python ci/validate_key_methods.py --src src/cf --skills-dir .claude/skills
"""

import argparse
import importlib.util
import re
import sys
from pathlib import Path

# Force UTF-8 output (Windows console defaults to cp1251)
for _stream in (sys.stdout, sys.stderr):
    _reconf = getattr(_stream, "reconfigure", None)
    if _reconf is not None:
        try:
            _reconf(encoding="utf-8")
        except (TypeError, ValueError):
            pass


# ---------------------------------------------------------------------------
# Parser import: load parse_export_methods from the single BSP skill script.
# The unified `bsp/` skill ships one search script (bsp_api.py); it exports
# parse_export_methods(bsl_path) -> [(name, region, sig_text, doc_lines), …]
# with region = the real #Область name (ПрограммныйИнтерфейс is stable).
# ---------------------------------------------------------------------------

def _load_parser(skills_dir):
    """Load the BSP skill search script and return (parse_fn, module)."""
    script_path = skills_dir / "bsp" / "scripts" / "bsp_api.py"
    if not script_path.is_file():
        raise RuntimeError(f"BSP skill script not found: {script_path}")
    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module spec from {script_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.parse_export_methods, mod


# The single BSP skill documents common-module exports in its references/.
# Other skill directories (agents-best-practices, opencode-runner,
# prompt-crafting-guide, …) use the same `Word.Word` syntax for documentation
# cross-references (file names, section titles) and would produce false
# positives — hence the allow-list.
BSP_CLUSTER_DIRS = frozenset({
    "bsp",
})

# Region names that mark a stable export (from bsp_api.STABLE_REGION).
STABLE_REGION_NAME = "ПрограммныйИнтерфейс"


# ---------------------------------------------------------------------------
# Markdown table parser: extract Module.Method + stability from key-methods.md
# ---------------------------------------------------------------------------

# A table cell like `ОбщегоНазначения.СообщитьПользователю` or
# `УправлениеПечатью.СформироватьПечатныеФормы` (in backticks).
RE_METHOD_CELL = re.compile(
    r"`(?P<module>[A-Za-zА-Яа-яЁё0-9_]+)\.(?P<method>[A-Za-zА-Яа-яЁё0-9_]+)`"
)

# 1C metadata object type prefixes that should NOT be treated as
# Module.Method calls. These appear in skills as references to metadata
# objects (registers, constants, scheduled jobs, catalog refs, common forms)
# and use the same `Type.Name` syntax, but are not common-module exports.
METADATA_TYPE_PREFIXES = frozenset({
    # English forms (configuration export / English metadata API)
    "InformationRegister", "Constant", "ScheduledJob", "Catalog",
    "CatalogRef", "Document", "DocumentRef", "ChartOfCharacteristicTypes",
    "ChartOfCharacteristicTypesRef", "InformationRegisterRecord",
    "CatalogObject", "DocumentObject", "Enum", "EnumRef",
    "CatalogManager", "DocumentManager", "InformationRegisterManager",
    "ConstantManager", "ConstantValueManager", "Task", "TaskRef",
    "Sequence", "SequenceRecord", "ExchangePlan", "ExchangePlanRef",
    "CalculationRegister", "CalculationRegisterRecord",
    "AccumulationRegister", "AccumulationRegisterRecord",
    "AccountingRegister", "AccountingRegisterRecord",
    "ChartOfCalculationTypes", "ChartOfCalculationTypesRef",
    "BusinessProcess", "BusinessProcessRef", "BusinessProcessObject",
    "BusinessProcessRoute", "BusinessProcessRoutePoint",
    "CatalogSelection", "DocumentSelection", "InformationRegisterSelection",
    "CommonForm", "CommonTemplate", "CommonModule", "CommonPicture",
    "CommonAttribute", "FilterTemplate", "DataProcessor", "Report",
    "SettingsStorage", "Cube", "CubeDimensionTable", "Table",
    "Characteristic", "ExternalDataProcessor", "ExternalReport",
    "HTTPService", "WebService", "Bot",
    # Russian forms (platform 1C:Предприятие Russian metadata API)
    "РегистрСведений", "РегистрНакопления", "РегистрБухгалтерии",
    "РегистрРасчета", "Константа", "РегламентноеЗадание",
    "Справочник", "СправочникСсылка", "СправочникОбъект",
    "СправочникМенеджер", "СправочникНаборЗаписей", "СправочникВыборка",
    "Документ", "ДокументСсылка", "ДокументОбъект", "ДокументМенеджер",
    "ДокументВыборка", "ДокументНаборЗаписей",
    "ПланВидовХарактеристик", "ПланВидовХарактеристикСсылка",
    "ПланВидовРасчета", "ПланВидовРасчетаСсылка",
    "ПланСчетов", "ПланСчетовСсылка",
    "ПланОбмена", "ПланОбменаСсылка",
    "Перечисление", "ПеречислениеСсылка",
    "Последовательность", "ПоследовательностьНаборЗаписей",
    "Перерасчет", "БизнесПроцесс", "БизнесПроцессСсылка",
    "БизнесПроцессОбъект", "Задача", "ЗадачаСсылка", "ЗадачаОбъект",
    "ОбщаяФорма", "ОбщийМакет", "ОбщийМодуль", "ОбщаяКартинка",
    "ОбщийРеквизит", "ОбработкаВыбор", "Отчет", "Обработка",
    "ХранилищеНастроек", "Куб", "ТаблицаИзмерений", "Таблица",
    "Характеристика", "ВнешняяОбработка", "ВнешнийОтчет",
    "HTTPСервис", "WebСервис", "Бот",
    "ФункциональнаяОпция", "ПараметрСеанса", "КритерийОтбора",
    "ПодпискаНаСобытие", "РегламентноеЗаданиеМенеджер",
    "РегистрСведенийМенеджер", "РегистрСведенийВыборка",
    "РегистрСведенийНаборЗаписей", "РегистрСведенийЗапись",
    "РегистрНакопленияМенеджер", "РегистрНакопленияВыборка",
    "РегистрНакопленияНаборЗаписей", "РегистрНакопленияЗапись",
    "СправочникСсылка.", "ДокументСсылка.",
    "ОпределяемыйТип", "ПолноеИмя", "Метаданные",
})


def is_metadata_reference(module_name):
    """Return True if `module_name` is a 1C metadata object type, not a
    common module. Such `Type.Name` cells describe metadata objects
    (registers, constants, scheduled jobs, catalog refs, common forms, …)
    and must not be validated as Module.Method exports."""
    return module_name in METADATA_TYPE_PREFIXES

# File-name extensions that, as the "method" part of a `Word.Word` token,
# mark a reference to a sibling file (e.g. `prefixes.md`, `base-common.md`)
# rather than a common-module export. These must not be validated.
FILE_EXTENSIONS = frozenset({
    "md", "bsl", "xml", "json", "py", "txt", "html", "htm", "yml", "yaml",
    "jpeg", "jpg", "png", "gif", "svg", "csv", "tsv", "log",
})

# Stability markers found anywhere in a row.
STABLE_MARKERS = {"стабильный", "стабильная", "✅ стабильный", "✅ стабильная"}
UNSTABLE_MARKERS = {"служебный", "⚠️ служебный", "служебная", "⚠️ служебная"}


def parse_key_methods_table(md_path):
    """Yield (module, method, declared_stable: bool|None, raw_row: str).

    declared_stable: True = stable, False = unstable/служебный,
    None = could not determine (skip validation).
    """
    text = md_path.read_text(encoding="utf-8")
    in_table = False
    header_seen = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and "---" in stripped:
            in_table = True
            header_seen = True
            continue
        if not in_table:
            continue
        if not stripped.startswith("|"):
            in_table = False
            continue
        # It's a table row
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        row_text = stripped
        # Find the first Module.Method in backticks
        m = RE_METHOD_CELL.search(row_text)
        if not m:
            continue
        module = m.group("module")
        method = m.group("method")
        # Skip 1C metadata object references (InformationRegister.X,
        # Constant.X, СправочникСсылка.X, ОбщаяФорма.X, …) — they are not
        # common-module exports and cannot be validated against source.
        if is_metadata_reference(module):
            continue
        # Skip sibling-file references (`prefixes.md`, `base-common.md`, …):
        # the "method" part is a file extension, not a method name.
        if method.lower() in FILE_EXTENSIONS:
            continue
        # Determine declared stability. The "Стабильность" column is not
        # fixed-position across skill files: in some tables it is the last
        # column, in others it precedes "Назначение"/"Пример". We scan every
        # cell for a stability marker, but only accept a cell as the
        # "stability" cell when its content is dominated by the marker (i.e.
        # the marker is most of what the cell says) — this prevents a long
        # "Назначение" cell that incidentally mentions "стабильная обёртка"
        # from being mistaken for the stability verdict.
        # Priority: if any short cell (< 40 chars) carries an unstable
        # marker, verdict = unstable. Else if any short cell carries a
        # stable marker, verdict = stable. Else fall back to whole-row scan.
        is_stable_decl = None
        for c in cells:
            cl = c.lower()
            if len(c) < 40 and any(m.lower() in cl for m in UNSTABLE_MARKERS):
                is_stable_decl = False
                break
            if len(c) < 40 and any(m.lower() in cl for m in STABLE_MARKERS):
                is_stable_decl = True
                # don't break — a later short cell may carry an unstable
                # marker that overrides this.
        if is_stable_decl is None:
            # No dedicated short stability cell: fall back to whole-row scan.
            lower_row = row_text.lower()
            if any(marker.lower() in lower_row for marker in STABLE_MARKERS):
                is_stable_decl = True
            elif any(marker.lower() in lower_row for marker in UNSTABLE_MARKERS):
                is_stable_decl = False
        yield (module, method, is_stable_decl, row_text)


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------

def find_module_in_src(src, module_name):
    """Return bsl_path for module_name, or None if not in the export."""
    cm_dir = Path(src) / "CommonModules"
    if not cm_dir.is_dir():
        return None
    for entry in sorted(cm_dir.iterdir()):
        if entry.is_dir() and entry.name == module_name:
            bsl = entry / "Ext" / "Module.bsl"
            return bsl if bsl.is_file() else None
    return None


def validate(md_path, src, parse_fn):
    """Validate one reference file's `Module.Method` mentions against src.

    parse_fn: bsp_api.parse_export_methods — returns
    [(method_name, region, sig_text, doc_lines), …]. A method is stable iff
    its region == ПрограммныйИнтерфейс.
    """
    issues = []
    for module, method, declared_stable, raw_row in parse_key_methods_table(md_path):
        bsl_path = find_module_in_src(src, module)
        if bsl_path is None:
            issues.append({
                "file": str(md_path),
                "module": module,
                "method": method,
                "severity": "ERROR",
                "message": f"module '{module}' not found in src",
                "row": raw_row,
            })
            continue
        # Parse the real module (all regions, exports only).
        methods = parse_fn(bsl_path)
        found = None
        for m_name, region, _sig, _doc in methods:
            if m_name == method:
                found = (region,)
                break
        if found is None:
            issues.append({
                "file": str(md_path),
                "module": module,
                "method": method,
                "severity": "ERROR",
                "message": f"method '{module}.{method}' not found as export in {bsl_path}",
                "row": raw_row,
            })
            continue
        (region,) = found
        is_stable_actual = (region == STABLE_REGION_NAME)
        if declared_stable is None:
            # Reference didn't declare stability — skip region check (we still
            # confirmed the method exists, which is the main guard against
            # hallucinated method/module names).
            continue
        if declared_stable and not is_stable_actual:
            severity = "ERROR" if region is None else "WARN"
            region_label = region or "(вне отслеживаемых областей)"
            issues.append({
                "file": str(md_path),
                "module": module,
                "method": method,
                "severity": severity,
                "message": (
                    f"declared 'стабильный' but actually in region "
                    f"'{region_label}' (module: {module})"
                ),
                "row": raw_row,
            })
        elif not declared_stable and is_stable_actual:
            issues.append({
                "file": str(md_path),
                "module": module,
                "method": method,
                "severity": "INFO",
                "message": (
                    f"declared 'служебный' but actually in 'ПрограммныйИнтерфейс' "
                    f"(over-conservative; module: {module})"
                ),
                "row": raw_row,
            })
    return issues


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate key-methods tables against BSP source code")
    parser.add_argument("--src", required=True,
                        help="Path to configuration export root (must contain CommonModules/)")
    parser.add_argument("--skills-dir", default=".claude/skills",
                        help="Path to skills directory (default: .claude/skills)")
    parser.add_argument("--strict", action="store_true",
                        help="Treat INFO-level findings as errors (exit 1)")
    args = parser.parse_args()

    src = Path(args.src)
    if not src.is_dir():
        print(f"Error: --src path does not exist: {src}", file=sys.stderr)
        sys.exit(2)
    cm = src / "CommonModules"
    if not cm.is_dir():
        print(f"Error: --src has no CommonModules/ subdir: {src}", file=sys.stderr)
        sys.exit(2)

    skills_dir = Path(args.skills_dir)
    if not skills_dir.is_dir():
        print(f"Error: --skills-dir not found: {skills_dir}", file=sys.stderr)
        sys.exit(2)

    parse_fn, _bsp_mod = _load_parser(skills_dir)

    # Find all *.md files in references/ that contain `Module.Method` mentions.
    # Only the BSP skill documents common-module exports; other skill
    # directories use the same `Word.Word` syntax for documentation
    # cross-references and would produce false positives.
    md_files = sorted(
        f for f in skills_dir.glob("*/references/*.md")
        if f.parent.parent.name in BSP_CLUSTER_DIRS
    )

    print(f"Validating {len(md_files)} reference file(s) from {skills_dir}/bsp "
          f"against {src}...")
    all_issues = []
    total_methods = 0
    for kmf in md_files:
        # Count `Module.Method` mentions found in this file.
        methods_in_file = list(parse_key_methods_table(kmf))
        if not methods_in_file:
            continue
        total_methods += len(methods_in_file)
        print(f"\n=== {kmf} ({len(methods_in_file)} methods) ===")
        issues = validate(kmf, src, parse_fn)
        all_issues.extend(issues)
        if not issues:
            print("  OK")
        else:
            for iss in issues:
                sev = iss["severity"]
                print(f"  [{sev}] {iss['module']}.{iss['method']}: {iss['message']}")

    # Summary
    errors = [i for i in all_issues if i["severity"] == "ERROR"]
    warns = [i for i in all_issues if i["severity"] == "WARN"]
    infos = [i for i in all_issues if i["severity"] == "INFO"]
    print(f"\n--- Summary ---")
    print(f"Methods checked: {total_methods}")
    print(f"  ERROR: {len(errors)}")
    print(f"  WARN:  {len(warns)}")
    print(f"  INFO:  {len(infos)}")

    if errors:
        print("\nFAIL: errors found (see above).", file=sys.stderr)
        sys.exit(1)
    if args.strict and (warns or infos):
        print("\nFAIL: --strict mode, warnings/info treated as errors.",
              file=sys.stderr)
        sys.exit(1)
    if warns:
        print("\nWarnings present (not fatal).")
    sys.exit(0)


if __name__ == "__main__":
    main()