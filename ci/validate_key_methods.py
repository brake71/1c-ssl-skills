#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate BSP API claims embedded in the unified ``bsp`` skill.

The reference files express checkable API claims as inline code spans:

    `Модуль.Метод(Параметры) Экспорт`

The validator extracts those claims from every reference file, enforces a
non-zero coverage floor, and (when ``--src`` is supplied) compares each claim
with the exported methods in a BSP configuration dump.

Explicit nearby wording such as "не существует" or "не экспортируется" turns
a claim into a negative assertion: validation succeeds only while the method
is not a public export. This keeps anti-hallucination examples testable too.

Exit codes: 0 = pass; 1 = validation/coverage failure; 2 = bad arguments/paths.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8")
        except (TypeError, ValueError):
            pass


DEFAULT_MIN_CLAIMS = 600
DEFAULT_MIN_FILES = 23
DEFAULT_MIN_COVERAGE = 95.0

STABLE_REGION_NAME = "ПрограммныйИнтерфейс"
TRACKED_REGIONS = (
    STABLE_REGION_NAME,
    "СлужебныйПрограммныйИнтерфейс",
    "СлужебныеПроцедурыИФункции",
    "УстаревшиеПроцедурыИФункции",
    "ПереопределениеВызовов",
    "ПереопределениеТекстаЗапросаНабораДанных",
)

# Match an inline call/signature and keep everything inside the same code span.
RE_INLINE_CALL = re.compile(
    r"`(?P<module>[A-Za-zА-Яа-яЁё0-9_]+)\."
    r"(?P<method>[A-Za-zА-Яа-яЁё0-9_]+)\s*\((?P<tail>[^`]*)`"
)

# Metadata namespaces and ordinary variables can also look like Module.Method.
# They are deliberately excluded before calculating semantic coverage.
METADATA_TYPE_PREFIXES = frozenset({
    "InformationRegister", "Constant", "ScheduledJob", "Catalog",
    "CatalogRef", "Document", "DocumentRef", "ChartOfCharacteristicTypes",
    "ChartOfCharacteristicTypesRef", "InformationRegisterRecord",
    "CatalogObject", "DocumentObject", "Enum", "EnumRef", "Task", "TaskRef",
    "Sequence", "ExchangePlan", "CalculationRegister", "AccumulationRegister",
    "AccountingRegister", "ChartOfCalculationTypes", "BusinessProcess",
    "CommonForm", "CommonTemplate", "CommonModule", "CommonPicture",
    "CommonAttribute", "DataProcessor", "Report", "ExternalDataProcessor",
    "ExternalReport", "HTTPService", "WebService",
    "РегистрСведений", "РегистрНакопления", "РегистрБухгалтерии",
    "РегистрРасчета", "Константа", "РегламентноеЗадание", "Справочник",
    "СправочникСсылка", "СправочникОбъект", "Документ", "ДокументСсылка",
    "ДокументОбъект", "ПланВидовХарактеристик", "ПланВидовРасчета",
    "ПланСчетов", "ПланОбмена", "Перечисление", "Последовательность",
    "БизнесПроцесс", "БизнесПроцессСсылка", "БизнесПроцессОбъект", "Задача",
    "ЗадачаСсылка", "ОбщаяФорма", "ОбщийМакет", "ОбщийМодуль",
    "ОбщаяКартинка", "ОбщийРеквизит", "Отчет", "Обработка",
    "ХранилищеНастроек", "ВнешняяОбработка", "ВнешнийОтчет", "HTTPСервис",
    "WebСервис", "ФункциональнаяОпция", "ПараметрСеанса", "КритерийОтбора",
    "ПодпискаНаСобытие", "ОпределяемыйТип", "Метаданные", "РегистрыСведений",
    "Справочники", "Документы",
})

NON_COMMON_NAMESPACES = frozenset({
    # Illustrative placeholders and local variables used in examples.
    "Модуль", "Объект", "Файл", "Менеджер", "МенеджерОбъекта",
    "КомандыПечати",
    # Platform managers/global namespaces, not BSP common modules.
    "ФоновыеЗадания", "ВнешниеОбработки",
})

NEGATIVE_AFTER_PATTERNS = tuple(re.compile(pattern, re.IGNORECASE) for pattern in (
    r"не\s+существует",
    r"такого\s+метода[\s\S]{0,20}нет",
    r"метод\s+отсутств",
    r"не\s+экспортируется",
    r"без\s+`?Экспорт`?",
))
NEGATIVE_BEFORE_PATTERNS = tuple(re.compile(pattern, re.IGNORECASE) for pattern in (
    r"несуществующ",
    r"через\s+внутренн",
    r"неэкспортн",
))


@dataclass(frozen=True)
class ApiClaim:
    path: Path
    line: int
    module: str
    method: str
    expected_exported: bool
    expected_region: str | None
    raw: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (str(self.path), self.module, self.method)


@dataclass(frozen=True)
class ClaimCollection:
    claims: tuple[ApiClaim, ...]
    occurrences: int
    raw_unique: int
    ignored_unique: int
    files_with_claims: frozenset[Path]

    @property
    def coverage_percent(self) -> float:
        if self.raw_unique == 0:
            return 0.0
        return 100.0 * len(self.claims) / self.raw_unique


def _load_parser(skills_dir: Path):
    script_path = skills_dir / "bsp" / "scripts" / "bsp_api.py"
    if not script_path.is_file():
        raise RuntimeError(f"BSP skill script not found: {script_path}")
    spec = importlib.util.spec_from_file_location("bsp_api", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module spec from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_export_methods


def _after_current_sentence(text: str, match: re.Match[str], limit: int) -> str:
    """Return nearby text about this span, not the next sentence/claim."""
    after_end = min(len(text), match.end() + limit)
    next_call = RE_INLINE_CALL.search(text, match.end(), after_end)
    if next_call is not None:
        after_end = next_call.start()
    after = text[match.end():after_end]
    sentence_end = re.search(r"[.!?](?:\s|\n|$)", after)
    if sentence_end is not None:
        after = after[:sentence_end.end()]
    return after


def _is_explicit_negative(text: str, match: re.Match[str]) -> bool:
    # Text after the code span normally contains "method does not exist" /
    # "is not exported". Stop at the sentence boundary so a following
    # anti-example is not attached to the current valid method.
    after = _after_current_sentence(text, match, 220)

    # A few forms put "non-existent" or "internal" immediately before the span.
    line_start = text.rfind("\n", 0, match.start()) + 1
    before = text[max(line_start, match.start() - 90):match.start()]
    return (
        any(pattern.search(after) for pattern in NEGATIVE_AFTER_PATTERNS)
        or any(pattern.search(before) for pattern in NEGATIVE_BEFORE_PATTERNS)
    )


def _declared_region(text: str, match: re.Match[str]) -> str | None:
    """Read a region only when it is local to this particular code span.

    A whole Markdown paragraph may describe stable, service and deprecated
    methods together. Looking farther than the next code span would assign a
    neighbouring method's region to the current claim.
    """
    line_start = text.rfind("\n", 0, match.start()) + 1
    context = (
        text[max(line_start, match.start() - 100):match.start()]
        + _after_current_sentence(text, match, 260)
    )
    present = [region for region in TRACKED_REGIONS if region in context]
    return present[0] if len(present) == 1 else None


def collect_claims(md_paths: Iterable[Path]) -> ClaimCollection:
    """Extract and deduplicate inline API claims from Markdown files."""
    occurrences = 0
    raw_keys: set[tuple[str, str, str]] = set()
    ignored_keys: set[tuple[str, str, str]] = set()
    extracted: list[ApiClaim] = []

    for path in sorted(md_paths):
        text = path.read_text(encoding="utf-8")
        for match in RE_INLINE_CALL.finditer(text):
            occurrences += 1
            module = match.group("module")
            method = match.group("method")
            key = (str(path), module, method)
            raw_keys.add(key)
            if module in METADATA_TYPE_PREFIXES or module in NON_COMMON_NAMESPACES:
                ignored_keys.add(key)
                continue

            extracted.append(ApiClaim(
                path=path,
                line=text.count("\n", 0, match.start()) + 1,
                module=module,
                method=method,
                expected_exported=not _is_explicit_negative(text, match),
                expected_region=_declared_region(text, match),
                raw=match.group(0),
            ))

    # If one occurrence explicitly documents a method as absent/non-exported,
    # apply that expectation to duplicate mentions of the same method in the
    # same reference file.
    negative_keys = {claim.key for claim in extracted if not claim.expected_exported}
    grouped: dict[tuple[str, str, str], list[ApiClaim]] = {}
    for claim in extracted:
        grouped.setdefault(claim.key, []).append(claim)

    claims: list[ApiClaim] = []
    for key, group in grouped.items():
        first = min(group, key=lambda item: item.line)
        expected_exported = key not in negative_keys
        regions = {
            item.expected_region for item in group
            if item.expected_region is not None and item.expected_exported
        }
        expected_region = regions.pop() if expected_exported and len(regions) == 1 else None
        claims.append(ApiClaim(
            path=first.path,
            line=first.line,
            module=first.module,
            method=first.method,
            expected_exported=expected_exported,
            expected_region=expected_region,
            raw=first.raw,
        ))

    claims.sort(key=lambda item: (str(item.path), item.line, item.module, item.method))
    return ClaimCollection(
        claims=tuple(claims),
        occurrences=occurrences,
        raw_unique=len(raw_keys),
        ignored_unique=len(ignored_keys),
        files_with_claims=frozenset(claim.path for claim in claims),
    )


def evaluate_coverage(
    collection: ClaimCollection,
    min_claims: int,
    min_files: int,
    min_coverage: float,
) -> list[str]:
    issues = []
    if len(collection.claims) < min_claims:
        issues.append(
            f"unique API claims {len(collection.claims)} < required {min_claims}"
        )
    if len(collection.files_with_claims) < min_files:
        issues.append(
            f"reference files with claims {len(collection.files_with_claims)} "
            f"< required {min_files}"
        )
    if collection.coverage_percent < min_coverage:
        issues.append(
            f"classified coverage {collection.coverage_percent:.1f}% "
            f"< required {min_coverage:.1f}%"
        )
    return issues


def validate_claims(
    claims: Iterable[ApiClaim],
    src: Path,
    parse_fn: Callable[[Path], list[tuple[str, str | None, str, list[str]]]],
) -> tuple[list[dict[str, str | int]], int]:
    """Compare claims with exported methods in ``src/CommonModules``."""
    issues: list[dict[str, str | int]] = []
    checked = 0
    module_cache: dict[str, dict[str, set[str | None]] | None] = {}

    for claim in claims:
        if claim.module not in module_cache:
            bsl_path = src / "CommonModules" / claim.module / "Ext" / "Module.bsl"
            if not bsl_path.is_file():
                module_cache[claim.module] = None
            else:
                methods: dict[str, set[str | None]] = {}
                for name, region, _signature, _doc in parse_fn(bsl_path):
                    methods.setdefault(name, set()).add(region)
                module_cache[claim.module] = methods

        methods = module_cache[claim.module]
        regions = None if methods is None else methods.get(claim.method)
        checked += 1

        if not claim.expected_exported:
            if regions:
                issues.append(_issue(
                    claim,
                    "ERROR",
                    "documented as absent/non-exported, but it is an export "
                    f"in region(s): {', '.join(sorted(r or '(none)' for r in regions))}",
                ))
            continue

        if methods is None:
            issues.append(_issue(claim, "ERROR", "common module not found in src"))
            continue
        if not regions:
            issues.append(_issue(claim, "ERROR", "method not found as an export"))
            continue
        if claim.expected_region is not None and claim.expected_region not in regions:
            actual = ", ".join(sorted(region or "(none)" for region in regions))
            issues.append(_issue(
                claim,
                "ERROR",
                f"declared region '{claim.expected_region}', actual region(s): {actual}",
            ))
        elif claim.expected_region is None and None in regions:
            issues.append(_issue(
                claim,
                "WARN",
                "export is outside the tracked API regions",
            ))

    return issues, checked


def _issue(claim: ApiClaim, severity: str, message: str) -> dict[str, str | int]:
    return {
        "file": str(claim.path),
        "line": claim.line,
        "module": claim.module,
        "method": claim.method,
        "severity": severity,
        "message": message,
    }


def _integer_at_least(minimum: int):
    def parse(value: str) -> int:
        parsed = int(value)
        if parsed < minimum:
            raise argparse.ArgumentTypeError(f"must be at least {minimum}")
        return parsed
    return parse


def _coverage_percent(value: str) -> float:
    parsed = float(value)
    if parsed < DEFAULT_MIN_COVERAGE or parsed > 100:
        raise argparse.ArgumentTypeError(
            f"must be between {DEFAULT_MIN_COVERAGE:g} and 100"
        )
    return parsed


def _print_coverage(collection: ClaimCollection) -> None:
    print("--- Coverage ---")
    print(f"Inline occurrences:      {collection.occurrences}")
    print(f"Unique API-like tokens:  {collection.raw_unique}")
    print(f"Unique checked claims:   {len(collection.claims)}")
    print(f"Ignored namespaces:      {collection.ignored_unique}")
    print(f"Reference files covered: {len(collection.files_with_claims)}")
    print(f"Classified coverage:     {collection.coverage_percent:.1f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate BSP API claims and coverage")
    parser.add_argument(
        "--src",
        help="Path to configuration export root containing CommonModules/",
    )
    parser.add_argument(
        "--skills-dir",
        default=".claude/skills",
        help="Skills directory (default: .claude/skills)",
    )
    parser.add_argument(
        "--coverage-only",
        action="store_true",
        help="Check extraction/coverage floors without requiring BSP source",
    )
    parser.add_argument(
        "--min-claims",
        type=_integer_at_least(DEFAULT_MIN_CLAIMS),
        default=DEFAULT_MIN_CLAIMS,
    )
    parser.add_argument(
        "--min-files",
        type=_integer_at_least(DEFAULT_MIN_FILES),
        default=DEFAULT_MIN_FILES,
    )
    parser.add_argument(
        "--min-coverage",
        type=_coverage_percent,
        default=DEFAULT_MIN_COVERAGE,
        help="Required classified percentage, 95 <= value <= 100 (default: 95)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )
    args = parser.parse_args()

    skills_dir = Path(args.skills_dir)
    references_dir = skills_dir / "bsp" / "references"
    if not references_dir.is_dir():
        print(f"Error: references directory not found: {references_dir}", file=sys.stderr)
        sys.exit(2)

    md_paths = sorted(references_dir.glob("*.md"))
    collection = collect_claims(md_paths)
    _print_coverage(collection)
    coverage_issues = evaluate_coverage(
        collection,
        min_claims=args.min_claims,
        min_files=args.min_files,
        min_coverage=args.min_coverage,
    )
    if coverage_issues:
        for issue in coverage_issues:
            print(f"[COVERAGE] {issue}", file=sys.stderr)
        sys.exit(1)

    if args.coverage_only:
        print("PASS: coverage floors satisfied.")
        sys.exit(0)

    if not args.src:
        print("Error: --src is required unless --coverage-only is used.", file=sys.stderr)
        sys.exit(2)
    src = Path(args.src)
    if not (src / "CommonModules").is_dir():
        print(f"Error: --src has no CommonModules/ subdir: {src}", file=sys.stderr)
        sys.exit(2)

    try:
        parse_fn = _load_parser(skills_dir)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    issues, checked = validate_claims(collection.claims, src, parse_fn)
    errors = [issue for issue in issues if issue["severity"] == "ERROR"]
    warnings = [issue for issue in issues if issue["severity"] == "WARN"]
    for issue in issues:
        print(
            f"[{issue['severity']}] {issue['file']}:{issue['line']} "
            f"{issue['module']}.{issue['method']}: {issue['message']}"
        )

    print("\n--- Semantic validation ---")
    print(f"Claims checked: {checked}")
    print(f"ERROR: {len(errors)}")
    print(f"WARN:  {len(warnings)}")

    if errors or (args.strict and warnings):
        print("FAIL: BSP API claims do not match source.", file=sys.stderr)
        sys.exit(1)
    print("PASS: BSP API claims match source.")


if __name__ == "__main__":
    main()
