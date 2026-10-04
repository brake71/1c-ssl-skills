#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run reproducible RED/GREEN behavioral evaluations for the BSP skill.

RED and GREEN use the same Codex CLI, model, prompt, and working directory.
The only intentional difference is the project-scoped skill staged at
``<workdir>/.agents/skills/bsp`` for GREEN. The runner never modifies a user
skill directory and refuses to overwrite an existing staged skill.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import shutil
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator


for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8")
        except (TypeError, ValueError):
            pass


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = REPO_ROOT / "evals" / "cases.json"
DEFAULT_REFERENCE_MATRIX = REPO_ROOT / "evals" / "reference-matrix.json"
DEFAULT_SKILL = REPO_ROOT / "skills" / "bsp"
DEFAULT_WORKDIR = REPO_ROOT / "src"
DEFAULT_BSL_SRC = REPO_ROOT / "src" / "cf"
DEFAULT_MODEL = "gpt-5.6-luna"
REPORT_SCHEMA_VERSION = 4
SKILL_CACHE_PATTERNS = ("__pycache__", "*.pyc", "*.pyo")
WINDOWS_READING_INSTRUCTIONS = (
    "Text files are UTF-8. On Windows, read them using rg -n . -- PATH "
    "or Python with encoding='utf-8'. Filter with native rg patterns, rg context "
    "options, or Python. Do not pipe native readers through PowerShell cmdlets "
    "such as Select-String, Select-Object, or Where-Object: they re-encode stdout. "
    "Use these UTF-8 native readers instead of PowerShell Get-Content: its "
    "OEM-encoded stdout is decoded as UTF-8 by the tool and corrupts Cyrillic."
)
SERVICE_REGIONS = frozenset({
    "СлужебныйПрограммныйИнтерфейс",
    "СлужебныеПроцедурыИФункции",
    "УстаревшиеПроцедурыИФункции",
})
MEMBER_REFERENCE_RE = re.compile(
    r"(?<![\w.])(?P<module>[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_]*)\s*\.\s*"
    r"(?P<method>[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)"
)
CALL_RE = re.compile(MEMBER_REFERENCE_RE.pattern + r"\s*\(")
MEMBER_ACCESS_RE = re.compile(
    r"(?<=[A-Za-zА-Яа-яЁё0-9_])\s*\.\s*(?=[A-Za-zА-Яа-яЁё_])"
)
READ_COMMAND_RE = re.compile(
    r"(?:^|-command\s+[\"']?|[;&|]\s*|[\r\n]\s*)"
    r"(?P<reader>get-content|gc|cat|type|more|head|tail|sed|awk|rg|grep|select-string|"
    r"python(?:3(?:\.\d+)?)?(?:\.exe)?|py(?:\.exe)?)\b",
    re.I,
)
BSL_FENCE_RE = re.compile(r"```(?:bsl|1c)?\s*\n(?P<code>.*?)```", re.I | re.S)
NEGATIVE_BLOCK_RE = re.compile(
    r"(?:не\s+(?:следует|вызыва|существ|нужно|запуска|команд|долж|явля|подход)|"
    r"(?:публичн|метод|модул|вызов)[^.\n]{0,120}\bнет\b|нельзя|"
    r"\b(?:неправильн|ошибочн|неверн|ложн)"
    r"(?:ый|ая|ое|ые|ого|ому|ым|ом|ой|ую|ых|ыми|о|а|ы)\b|\bневерен\b|"
    r"антипаттерн|запрещ(?:[её]н\w*|\w*\s+вызыв\w*))",
    re.I,
)
NEGATIVE_CONNECTOR_RE = re.compile(r"^(?:или|либо|и|or|and)\s*[:;,.]?$", re.I)
INFRASTRUCTURE_PATTERNS = (
    ("quota_or_rate_limit", re.compile(r"quota|rate[ _-]?limit|too many requests", re.I)),
    ("authentication", re.compile(r"auth(?:entication|orization)?|unauthorized|forbidden|login", re.I)),
    ("network", re.compile(r"network|connection|dns|socket|proxy|tls|certificate", re.I)),
    ("model_unavailable", re.compile(r"model[^\n]{0,80}(?:unavailable|not found|unsupported)|no such model", re.I)),
)


class EvalError(RuntimeError):
    """An evaluation setup or execution error."""


@dataclass(frozen=True)
class EvalCase:
    id: str
    task: str
    reference: str | None
    should_trigger: bool
    requires_bsl: bool
    required_patterns: tuple[str, ...]
    forbidden_patterns: tuple[str, ...]
    activation_patterns: tuple[str, ...]
    required_code_patterns: tuple[str, ...] = ()
    required_code_block_patterns: tuple[str, ...] = ()
    forbidden_code_patterns: tuple[str, ...] = ()
    error_handling_rule: ErrorHandlingRule | None = None


@dataclass(frozen=True)
class ErrorHandlingRule:
    value: str
    source_call: str
    normal_values: tuple[str, ...]


@dataclass(frozen=True)
class MethodInfo:
    region: str | None
    signature: str


def load_cases(path: Path) -> list[EvalCase]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalError(f"Cannot read eval corpus {path}: {exc}") from exc
    if payload.get("version") != 1 or not isinstance(payload.get("cases"), list):
        raise EvalError("Eval corpus must contain version=1 and a cases array")

    result: list[EvalCase] = []
    seen: set[str] = set()
    for index, raw in enumerate(payload["cases"], start=1):
        if not isinstance(raw, dict):
            raise EvalError(f"Case #{index} must be an object")
        case_id = raw.get("id")
        if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", case_id):
            raise EvalError(f"Case #{index} has invalid id: {case_id!r}")
        if case_id in seen:
            raise EvalError(f"Duplicate case id: {case_id}")
        seen.add(case_id)
        required = _pattern_tuple(raw, "required_patterns", case_id)
        forbidden = _pattern_tuple(raw, "forbidden_patterns", case_id, required=False)
        activation = _pattern_tuple(raw, "activation_patterns", case_id, required=False)
        required_code = _pattern_tuple(
            raw, "required_code_patterns", case_id, required=False
        )
        required_code_blocks = _pattern_tuple(
            raw, "required_code_block_patterns", case_id, required=False
        )
        forbidden_code = _pattern_tuple(
            raw, "forbidden_code_patterns", case_id, required=False
        )
        rule_raw = raw.get("error_handling_rule")
        error_rule = None
        if rule_raw is not None:
            if (not isinstance(rule_raw, dict)
                    or not isinstance(rule_raw.get("value"), str)
                    or not re.fullmatch(r"[\wА-Яа-яЁё]+(?:\.[\wА-Яа-яЁё]+)+", rule_raw["value"])
                    or not isinstance(rule_raw.get("source_call"), str)
                    or not re.fullmatch(r"[\wА-Яа-яЁё]+(?:\.[\wА-Яа-яЁё]+)+", rule_raw["source_call"])
                    or set(rule_raw) != {"value", "source_call", "normal_values"}
                    or not isinstance(rule_raw.get("normal_values"), list)
                    or not 1 <= len(rule_raw["normal_values"]) <= 16
                    or "" not in rule_raw["normal_values"]
                    or not all(isinstance(v, str) for v in rule_raw["normal_values"])):
                raise EvalError(f"Case {case_id} has invalid error_handling_rule")
            error_rule = ErrorHandlingRule(rule_raw["value"], rule_raw["source_call"], tuple(rule_raw["normal_values"]))
        for pattern in (
            required + forbidden + activation + required_code + required_code_blocks
            + forbidden_code
        ):
            try:
                re.compile(pattern, re.I | re.S)
            except re.error as exc:
                raise EvalError(f"Invalid regex in {case_id}: {pattern!r}: {exc}") from exc
        task = raw.get("task")
        if not isinstance(task, str) or not task.strip():
            raise EvalError(f"Case {case_id} has no task")
        result.append(EvalCase(
            id=case_id,
            task=task.strip(),
            reference=raw.get("reference"),
            should_trigger=bool(raw.get("should_trigger", True)),
            requires_bsl=bool(raw.get("requires_bsl", False)),
            required_patterns=required,
            forbidden_patterns=forbidden,
            activation_patterns=activation,
            required_code_patterns=required_code,
            required_code_block_patterns=required_code_blocks,
            forbidden_code_patterns=forbidden_code,
            error_handling_rule=error_rule,
        ))
    if not result:
        raise EvalError("Eval corpus is empty")
    return result


def load_reference_matrix(path: Path) -> tuple[dict[str, list[str]], list[str]]:
    """Load the checked-in reference -> eval case coverage manifest."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalError(f"Cannot read reference matrix {path}: {exc}") from exc
    references = payload.get("references")
    unscoped = payload.get("unscoped_cases")
    if payload.get("version") != 1 or not isinstance(references, dict):
        raise EvalError("Reference matrix must contain version=1 and a references object")
    if not isinstance(unscoped, list):
        raise EvalError("Reference matrix must contain an unscoped_cases array")
    for reference, case_ids in references.items():
        if not isinstance(reference, str) or not reference.endswith(".md"):
            raise EvalError(f"Invalid reference matrix key: {reference!r}")
        if not isinstance(case_ids, list) or not all(
            isinstance(case_id, str) and case_id for case_id in case_ids
        ):
            raise EvalError(f"Reference {reference} must map to an array of case ids")
    if not all(isinstance(case_id, str) and case_id for case_id in unscoped):
        raise EvalError("unscoped_cases must contain case ids")
    return references, unscoped


def validate_reference_matrix(
    cases: list[EvalCase],
    references: dict[str, list[str]],
    unscoped_cases: list[str],
    references_dir: Path,
) -> dict[str, list[str]]:
    """Require the manifest, corpus, and shipped reference files to agree exactly."""
    if not references_dir.is_dir():
        raise EvalError(f"References directory not found: {references_dir}")
    shipped = {path.name for path in references_dir.glob("*.md") if path.is_file()}
    declared = set(references)
    if missing := sorted(shipped - declared):
        raise EvalError(f"Reference matrix is missing: {', '.join(missing)}")
    if unknown := sorted(declared - shipped):
        raise EvalError(f"Reference matrix names unknown files: {', '.join(unknown)}")

    cases_by_id = {case.id: case for case in cases}
    assignments: dict[str, str | None] = {}
    for reference, case_ids in references.items():
        for case_id in case_ids:
            if case_id in assignments:
                raise EvalError(f"Eval case occurs more than once in reference matrix: {case_id}")
            assignments[case_id] = reference
    for case_id in unscoped_cases:
        if case_id in assignments:
            raise EvalError(f"Eval case occurs more than once in reference matrix: {case_id}")
        assignments[case_id] = None

    if missing := sorted(set(cases_by_id) - set(assignments)):
        raise EvalError(f"Reference matrix does not assign eval cases: {', '.join(missing)}")
    if unknown := sorted(set(assignments) - set(cases_by_id)):
        raise EvalError(f"Reference matrix names unknown eval cases: {', '.join(unknown)}")
    for case_id, assigned_reference in assignments.items():
        corpus_reference = cases_by_id[case_id].reference
        if corpus_reference != assigned_reference:
            raise EvalError(
                f"Reference matrix assigns {case_id} to {assigned_reference!r}, "
                f"but corpus declares {corpus_reference!r}"
            )
    return {reference: list(case_ids) for reference, case_ids in references.items()}


def _pattern_tuple(
    raw: dict, key: str, case_id: str, *, required: bool = True
) -> tuple[str, ...]:
    value = raw.get(key, [] if not required else None)
    if not isinstance(value, list) or (required and not value):
        raise EvalError(f"Case {case_id} must define a non-empty {key} array")
    if not all(isinstance(item, str) and item for item in value):
        raise EvalError(f"Case {case_id} has invalid values in {key}")
    return tuple(value)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def skill_sha256(skill_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        (item for item in skill_dir.rglob("*")
         if item.is_file() and not any(
             fnmatch.fnmatchcase(part, pattern)
             for part in item.relative_to(skill_dir).parts
             for pattern in SKILL_CACHE_PATTERNS
         )),
        key=lambda item: item.relative_to(skill_dir).as_posix(),
    ):
        digest.update(path.relative_to(skill_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def validate_skill(skill_dir: Path) -> str:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise EvalError(f"SKILL.md not found: {skill_md}")
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(?P<frontmatter>.*?)\n---\s*\n", text, re.S)
    if not match:
        raise EvalError(f"Invalid frontmatter in {skill_md}")
    name_match = re.search(r"^name:\s*[\"']?([^\"'\s]+)", match.group("frontmatter"), re.M)
    description_match = re.search(r"^description:\s*(.+)$", match.group("frontmatter"), re.M)
    if not name_match or not description_match:
        raise EvalError("Skill frontmatter must contain name and description")
    name = name_match.group(1)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name):
        raise EvalError(f"Invalid skill name: {name}")
    return name


def load_method_index(skill_dir: Path, bsl_src: Path | None) -> dict[str, dict[str, MethodInfo]]:
    if bsl_src is None:
        return {}
    common_modules = bsl_src / "CommonModules"
    if not common_modules.is_dir():
        raise EvalError(f"BSL source has no CommonModules directory: {bsl_src}")
    parser_path = skill_dir / "scripts" / "bsp_api.py"
    spec = importlib.util.spec_from_file_location("bsp_api_for_evals", parser_path)
    if spec is None or spec.loader is None:
        raise EvalError(f"Cannot load BSP API parser: {parser_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    index: dict[str, dict[str, MethodInfo]] = {}
    for module_path in sorted(common_modules.glob("*/Ext/Module.bsl")):
        methods: dict[str, MethodInfo] = {}
        for (method, region, signature, _doc,
             _start_line, _end_line) in module.parse_export_methods(module_path):
            methods[method] = MethodInfo(region=region, signature=signature)
        index[module_path.parents[1].name] = methods
    return index


def extract_jsonl(stdout: str) -> tuple[list[dict], list[str]]:
    events: list[dict] = []
    noise: list[str] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            noise.append(line)
            continue
        if isinstance(value, dict):
            events.append(value)
        else:
            noise.append(line)
    return events, noise


def final_message(events: Iterable[dict]) -> str:
    messages = []
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = event.get("item") or {}
        if item.get("type") == "agent_message" and isinstance(item.get("text"), str):
            messages.append(item["text"])
    return messages[-1] if messages else ""


def usage_from_events(events: Iterable[dict]) -> dict[str, int]:
    usage: dict[str, int] = {}
    for event in events:
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = {
                key: int(value)
                for key, value in event["usage"].items()
                if isinstance(value, (int, float))
            }
    return usage


def read_command_segment(text: str, start: int) -> str:
    """Take one reader's arguments without following another shell command."""
    quote = None
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if quote == '"' and char == "\\":
            escaped = True
            continue
        if char in "\"'":
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
        elif quote is None and char in ";&|\r\n":
            return text[start:index]
    return text[start:]


def search_reader_targets(arguments: list[str]) -> list[str]:
    """Identify file operands, excluding rg/grep patterns and option values."""
    non_content = {"--files", "--files-with-matches", "--files-without-match",
                   "--count", "--count-matches", "--quiet"}
    pattern_options = {"-e", "--regexp", "-f", "--file"}
    value_options = pattern_options | {
        "-g", "--glob", "--iglob", "-t", "--type", "-T", "--type-not",
        "-A", "-B", "-C", "--after-context", "--before-context", "--context",
        "-m", "--max-count", "-r", "--replace", "--encoding", "--color",
        "--max-columns", "--max-depth", "--max-filesize", "--threads", "-j",
        "--dfa-size-limit", "--regex-size-limit", "--sort", "--sortr",
        "--path-separator", "--type-add", "--type-clear", "--engine",
    }
    operands = []
    explicit_pattern = False
    options = True
    index = 0
    while index < len(arguments):
        word = arguments[index]
        index += 1
        if options and word == "--":
            options = False
        elif options and word.startswith("-"):
            option, equals, _value = word.partition("=")
            if option in non_content or re.fullmatch(r"-[a-zA-Z]*[clLq][a-zA-Z]*", word):
                return []
            if option in pattern_options or word.startswith(("-e", "-f")):
                explicit_pattern = True
            if option in value_options and not equals:
                index += 1
        else:
            operands.append(word)
    return operands if explicit_pattern else operands[1:]


def python_reader_targets(arguments: list[str]) -> list[str]:
    """Infer literal file reads whose text reaches a top-level print expression."""
    try:
        code = arguments[arguments.index("-c") + 1]
        module = ast.parse(code)
    except (ValueError, IndexError, SyntaxError):
        return []

    # Values are deliberately small abstract states; unknown syntax never adds evidence.
    env: dict[str, tuple] = {}
    targets: list[str] = []
    factories = {"Path": True, "open": True, "print": True}

    def evaluate(node: ast.AST, scope: dict[str, tuple] | None = None) -> tuple | None:
        names = env if scope is None else scope
        if isinstance(node, ast.Constant):
            return ("const", node.value)
        if isinstance(node, ast.Name):
            return names.get(node.id)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "Path" and factories["Path"] and node.args:
                value = evaluate(node.args[0], names)
                return ("path", frozenset({value[1]})) if value and value[0] == "const" and isinstance(value[1], str) else None
            if isinstance(func, ast.Name) and func.id == "open" and factories["open"] and node.args:
                value = evaluate(node.args[0], names)
                return ("file", frozenset({value[1]})) if value and value[0] == "const" and isinstance(value[1], str) else None
            if isinstance(func, ast.Attribute):
                source = evaluate(func.value, names)
                if source is None:
                    return None
                if func.attr == "read_text" and source[0] == "path":
                    return ("text", source[1])
                if func.attr == "read" and source[0] == "file":
                    if node.keywords or len(node.args) > 1:
                        return None
                    if node.args:
                        size = evaluate(node.args[0], names)
                        if not size or size[0] not in {"const", "number"} or not isinstance(size[1], int) or size[1] == 0:
                            return None
                    return ("text", source[1])
                if func.attr == "splitlines" and source[0] == "text":
                    return ("lines", source[1])
            if isinstance(func, ast.Attribute) and func.attr == "join":
                source = evaluate(func.value, names)
                if source and source[0] == "const" and isinstance(source[1], str) and len(node.args) == 1:
                    joined = evaluate(node.args[0], names)
                    return ("text", joined[1]) if joined and joined[0] == "itertext" else None
            return None
        if isinstance(node, ast.Subscript):
            source = evaluate(node.value, names)
            if source and source[0] == "text":
                if isinstance(node.slice, ast.Slice):
                    parts = [evaluate(part, names) for part in (node.slice.lower, node.slice.upper, node.slice.step) if part is not None]
                    if not all(part and part[0] in {"const", "number"} and isinstance(part[1], int) for part in parts):
                        return None
                    bounds = [evaluate(part, names) if part is not None else None for part in (node.slice.lower, node.slice.upper, node.slice.step)]
                    start = bounds[0][1] if bounds[0] else 0
                    stop = bounds[1][1] if bounds[1] else None
                    step = bounds[2][1] if bounds[2] else 1
                    if start < 0 or (stop is not None and stop < 0) or step <= 0:
                        return None
                    if stop is not None and stop <= start:
                        return None
                return source
            if source and source[0] == "lines":
                index = node.slice
                if isinstance(index, ast.Slice):
                    parts = [evaluate(part, names) for part in (index.lower, index.upper, index.step) if part is not None]
                    valid = all(part and part[0] in {"const", "number"} and isinstance(part[1], int) for part in parts)
                    if valid:
                        bounds = [evaluate(part, names) if part is not None else None for part in (index.lower, index.upper, index.step)]
                        start = bounds[0][1] if bounds[0] else 0
                        stop = bounds[1][1] if bounds[1] else None
                        step = bounds[2][1] if bounds[2] else 1
                        valid = start >= 0 and (stop is None or stop >= 0) and step > 0
                        if valid and stop is not None and stop <= start:
                            return None
                else:
                    part = evaluate(index, names)
                    valid = bool(part and part[0] in {"const", "number"} and isinstance(part[1], int))
                return ("text", source[1]) if valid else None
            return None
        if isinstance(node, ast.JoinedStr):
            paths = set()
            for part in node.values:
                value = evaluate(part.value, names) if isinstance(part, ast.FormattedValue) else evaluate(part, names)
                if value and value[0] in {"text", "lines"}:
                    paths.update(value[1])
            return ("text", frozenset(paths)) if paths else ("const", "")
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
            left, right = evaluate(node.left, names), evaluate(node.right, names)
            if left and right and left[0] in {"const", "number"} and right[0] in {"const", "number"}:
                try:
                    value = left[1] + right[1] if isinstance(node.op, ast.Add) else left[1] - right[1]
                    return ("number", value) if isinstance(value, (int, float)) else None
                except TypeError:
                    return None
            return None
        if isinstance(node, ast.GeneratorExp) and len(node.generators) == 1:
            clause = node.generators[0]
            if clause.ifs:
                return None
            iterable = clause.iter
            values: list[tuple] = []
            if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name) and iterable.func.id == "range":
                if not isinstance(clause.target, ast.Name):
                    return None
                bounds = [evaluate(arg, names) for arg in iterable.args]
                if not 1 <= len(bounds) <= 3 or any(not b or b[0] not in {"const", "number"} or not isinstance(b[1], int) for b in bounds):
                    return None
                try:
                    sequence = range(*(b[1] for b in bounds))
                    if len(sequence) > 10000:
                        return None
                except (ValueError, OverflowError):
                    return None
                for item in sequence:
                    local = dict(names)
                    local[clause.target.id] = ("number", item)
                    value = evaluate(node.elt, local)
                    if value is None:
                        return None
                    values.append(value)
            elif isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name) and iterable.func.id == "enumerate" and iterable.args:
                source = evaluate(iterable.args[0], names)
                if not source or source[0] != "lines":
                    return None
                # Enumerated lines are represented symbolically; only line values carry provenance.
                target = clause.target
                if not isinstance(target, (ast.Tuple, ast.List)) or len(target.elts) != 2 or not all(isinstance(x, ast.Name) for x in target.elts):
                    return None
                local = dict(names)
                local[target.elts[0].id] = ("number", 0)
                local[target.elts[1].id] = ("text", source[1])
                value = evaluate(node.elt, local)
                if value is None:
                    return None
                values.append(value)
            else:
                return None
            paths = set().union(*(value[1] for value in values if value[0] in {"text", "lines"})) if values else set()
            return ("itertext", frozenset(paths)) if paths else None
        return None

    for statement in module.body:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            for alias in statement.names:
                if alias.name == "*":
                    return []
                bound = alias.asname or (alias.name if isinstance(statement, ast.ImportFrom)
                                         else alias.name.split(".", 1)[0])
                env.pop(bound, None)
                if bound in factories:
                    factories[bound] = bool(
                        isinstance(statement, ast.ImportFrom)
                        and alias.name == bound
                        and ((statement.module == "pathlib" and bound == "Path")
                             or (statement.module == "builtins" and bound in {"open", "print"}))
                    )
        elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
            if isinstance(statement, ast.AnnAssign) and statement.value is None:
                return []
            value = evaluate(statement.value) if statement.value is not None else None
            targets_to_bind = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            if not all(isinstance(target, ast.Name) for target in targets_to_bind):
                return []
            for target in targets_to_bind:
                if target.id in factories:
                    factories[target.id] = False
                if value is None:
                    env.pop(target.id, None)
                else:
                    env[target.id] = value
        elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if isinstance(call.func, ast.Name) and call.func.id == "print" and factories["print"]:
                if any(keyword.arg in {None, "file"} for keyword in call.keywords):
                    return []
                for argument in call.args:
                    value = evaluate(argument)
                    if value and value[0] in {"text", "lines"}:
                        targets.extend(value[1])
            else:
                return []
        else:
            return []
    return list(dict.fromkeys(targets))


def skill_activation_evidence(
    events: Iterable[dict], skill_name: str, reference: str | None = None
) -> list[str]:
    """Return observable reads of the staged skill or one exact reference."""
    skill_root = f".agents/skills/{skill_name.lower()}/"
    if reference is not None:
        expected_path = re.escape(f"{skill_root}references/{reference.lower()}")
        path_pattern = re.compile(
            rf"(?<![a-z0-9_.-]){expected_path}(?![a-z0-9_.-])"
        )
    else:
        skill_path = re.escape(skill_root)
        path_pattern = re.compile(
            rf"(?<![a-z0-9_.-]){skill_path}"
            rf"(?:skill\.md|references/[a-z0-9_-]+\.md)(?![a-z0-9_.-])"
        )

    evidence = []
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = event.get("item") or {}
        if item.get("type") != "command_execution":
            continue
        exit_code = item.get("exit_code")
        if exit_code is not None and exit_code != 0:
            continue
        command = str(item.get("command", ""))
        if not str(item.get("aggregated_output", "")).strip():
            continue
        body = command
        if re.search(r"\s-command\s", command, re.IGNORECASE):
            try:
                shell_arguments = shlex.split(command)
                command_index = next(
                    index for index, word in enumerate(shell_arguments)
                    if word.lower() == "-command"
                )
                body = shell_arguments[command_index + 1]
            except (ValueError, StopIteration, IndexError):
                continue
        for read in READ_COMMAND_RE.finditer(body):
            segment = read_command_segment(body, read.end())
            reader = read.group("reader").lower()
            targets = [segment]
            try:
                if reader in {"rg", "grep"}:
                    targets = search_reader_targets(shlex.split(segment.replace("\\", "/")))
                elif reader.startswith("python") or reader in {"py", "py.exe"}:
                    targets = python_reader_targets(shlex.split(segment))
                elif reader == "select-string" and re.search(r"(?:^|\s)-(?:list|quiet)\b", segment, re.IGNORECASE):
                    continue
            except ValueError:
                continue
            if not any(path_pattern.search(re.sub(r"/+", "/", target.replace("\\", "/").lower()))
                       for target in targets):
                continue
            if command not in evidence:
                evidence.append(command)
            break
    return evidence


def tool_output_decode_errors(events: Iterable[dict]) -> list[dict]:
    """Reject damaged tool text rather than score an answer based on unreadable input."""
    errors = []
    for event in events:
        item = event.get("item") or {}
        if (
            event.get("type") != "item.completed"
            or item.get("type") != "command_execution"
            or item.get("exit_code") not in (None, 0)
        ):
            continue
        output = str(item.get("aggregated_output", ""))
        # Codex can cut a UTF-8 code point at a native byte-truncation seam.
        # Only disregard the single replacement immediately beside its marker;
        # damage elsewhere (including a second replacement) still fails closed.
        seam = r"(?P<before>\ufffd)?(?P<marker>\r?\n\.\.\. \d+ bytes omitted \.\.\.\r?\n)(?P<after>\ufffd)?"
        def preserve_damage(match: re.Match) -> str:
            if bool(match.group("before")) + bool(match.group("after")) == 1:
                return match.group("marker")
            return match.group(0)
        output = re.sub(seam, preserve_damage, output)
        if replacement_characters := output.count("\ufffd"):
            errors.append({
                "command": str(item.get("command", "")),
                "replacement_characters": replacement_characters,
            })
    return errors


def bsl_code_views(code: str) -> tuple[str, str]:
    """Pair comment-free BSL with an aligned view masking string literals."""
    values = list(code)
    syntax = list(code)
    in_string = False
    index = 0
    while index < len(code):
        char = code[index]
        if in_string:
            if char not in "\r\n":
                syntax[index] = " "
            if char == '"':
                if index + 1 < len(code) and code[index + 1] == '"':
                    syntax[index + 1] = " "
                    index += 1
                else:
                    in_string = False
        elif char == '"':
            in_string = True
            syntax[index] = " "
        elif code.startswith("//", index):
            end = code.find("\n", index)
            end = len(code) if end < 0 else end
            for position in range(index, end):
                if code[position] not in "\r\n":
                    values[position] = syntax[position] = " "
            index = end - 1
        index += 1
    value_text, syntax_text = "".join(values), "".join(syntax)
    # Apply identical edits only to actual member access, not dotted text in
    # literals such as a handler name or a URL. The paired offsets stay aligned.
    for match in reversed(list(MEMBER_ACCESS_RE.finditer(syntax_text))):
        value_text = value_text[:match.start()] + "." + value_text[match.end():]
        syntax_text = syntax_text[:match.start()] + "." + syntax_text[match.end():]
    return value_text, syntax_text


def executable_pattern_hit(pattern: str, values: str, syntax: str) -> bool:
    """An assertion may inspect literal arguments but cannot start inside one."""
    for match in re.finditer(pattern, values, re.I | re.S):
        first_token = next((index for index in range(match.start(), match.end())
                            if not values[index].isspace()), None)
        if first_token is not None and not syntax[first_token].isspace():
            return True
    return False


def bsl_blocks(response: str) -> list[str]:
    blocks = [match.group("code") for match in BSL_FENCE_RE.finditer(response)]
    if blocks:
        return blocks
    if re.search(r"\b(?:Процедура|Функция)\b", response, re.I):
        return [response]
    return []


def warning_targets_same_call(context: str, code_syntax: str) -> bool:
    code_calls = {
        (call.group("module").lower(), call.group("method").lower())
        for call in CALL_RE.finditer(code_syntax)
    }
    for clause in re.split(r"(?<=[.!?;:])\s+", context):
        if not NEGATIVE_BLOCK_RE.search(clause):
            continue
        references = {
            (reference.group("module").lower(), reference.group("method").lower())
            for reference in MEMBER_REFERENCE_RE.finditer(clause)
        }
        if code_calls.intersection(references):
            return True
        # An unqualified warning such as "Метод() не следует вызывать"
        # also targets a call, but never collapse different qualified modules.
        if not references:
            names = set(re.findall(r"\b(\w+)\s*\(", clause.lower()))
            if names.intersection(method for _, method in code_calls):
                return True
    return False


def negative_example_context(context: str, code_syntax: str) -> bool:
    """Require evidence that a warning labels this snippet, not other advice."""
    if re.search(
        r"(?:ложн\w*|ошибочн\w*|неправильн\w*|неверн\w*)\s+"
        r"(?:очевидн\w*\s+)?(?:пример|код|вариант|вызов|API|реализац|сигнатур)\w*|"
        r"(?:пример|код|вариант|вызов)\w*\s+(?:неверн|ошибочн|неправильн)\w*|"
        r"(?:неверно|ошибочно|неправильно)\s*:\s*$|антипаттерн|нельзя\s+так|"
        r"\bтак\b[^.\n]{0,40}\bнельзя\b", context, re.I
    ):
        return True
    if warning_targets_same_call(context, code_syntax):
        return True
    if not NEGATIVE_BLOCK_RE.search(context):
        return False
    # Unnamed example labels still apply regardless of named references.
    if re.search(
        r"вызова?\s+вида|\bв\s+частности\b|\bнапример\b|"
        r"\bтаких\s+(?:публичных\s+)?(?:методов|вызовов)\b|"
        r"быть\s+не\s+долж", context, re.I
    ):
        return True
    deictic = re.search(r"\bэтот\s+(?:метод|вызов|код|пример)\b", context, re.I)
    if not deictic:
        return False
    # "`OtherMethod` returns ...; this method is internal" refers to the
    # named method, not the preceding fence. Resolve only explicit method
    # subjects/labels; an argument name or arbitrary inline code is no evidence.
    named = list(re.finditer(
        r"\b(?:метод|вызов)\s+`(?P<label>\w+(?:\.\w+)?)`|"
        r"`(?P<subject>\w+(?:\.\w+)?)`\s+(?:возвращает|находится|относится)\b",
        context[:deictic.start()], re.I
    ))
    if not named:
        return True
    target = (named[-1].group("label") or named[-1].group("subject")).lower()
    calls = {(call.group("module").lower(), call.group("method").lower())
             for call in CALL_RE.finditer(code_syntax)}
    return (tuple(target.split(".")) in calls if "." in target
            else any(method == target for _, method in calls))


def executable_bsl_blocks(response: str) -> list[str]:
    """Exclude fenced snippets explicitly presented as incorrect examples."""
    matches = list(BSL_FENCE_RE.finditer(response))
    if not matches:
        return bsl_blocks(response)
    negative = []
    for index, match in enumerate(matches):
        previous_end = matches[index - 1].end() if index else 0
        prefix = response[max(previous_end, match.start() - 240):match.start()]
        immediate_prefix = re.split(r"\n\s*\n", prefix.rstrip())[-1]
        prefix_paragraph = immediate_prefix
        sentences = re.split(r"(?<=[.!?])\s+", immediate_prefix)
        # A correction can contain "the advice is wrong" before the actual
        # recommendation. Use its nearest sentence, except connecting labels.
        if sentences and not re.fullmatch(r"(?:в частности|например)\s*[:.]?", sentences[-1], re.I):
            immediate_prefix = sentences[-1]
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(response)
        suffix = response[match.end():min(next_start, match.end() + 320)]
        immediate_suffix = re.split(r"\n\s*\n", suffix.lstrip())[0]
        code = match.group("code")
        first_comments = "\n".join(
            line for line in code.splitlines()[:3] if line.lstrip().startswith("//")
        )
        code_syntax = bsl_code_views(code)[1]
        suffix_negative = negative_example_context(immediate_suffix, code_syntax)
        if (index + 1 < len(matches) and immediate_suffix.rstrip().endswith(":")
                and immediate_suffix.strip() in response[match.end():matches[index + 1].start()]):
            # A heading introducing the next fence does not label this one.
            suffix_negative = False
        prefix_negative = (
            warning_targets_same_call(prefix_paragraph, code_syntax)
            or negative_example_context(immediate_prefix, code_syntax)
        )
        # A hook declaration is not a direct call. No implementation exemption
        # is needed: matching is against actual qualified calls in its body.
        negative.append(
            prefix_negative or suffix_negative
            or negative_example_context(first_comments, code_syntax)
        )

    # Propagate negative context across adjacent alternatives such as
    # ``bad_call_one(...)`` / "или" / ``bad_call_two(...)``.
    changed = True
    while changed:
        changed = False
        for index in range(len(matches) - 1):
            bridge = response[matches[index].end():matches[index + 1].start()].strip()
            if NEGATIVE_CONNECTOR_RE.fullmatch(bridge) and (
                negative[index] or negative[index + 1]
            ):
                if not negative[index] or not negative[index + 1]:
                    negative[index] = negative[index + 1] = True
                    changed = True

    return [
        match.group("code")
        for match, is_negative in zip(matches, negative)
        if not is_negative
    ]


def normalize_member_access(text: str) -> str:
    return MEMBER_ACCESS_RE.sub(".", text)


def error_handling_rule_satisfied(blocks: list[str], rule: ErrorHandlingRule) -> bool:
    """Interpret a bounded declarative subset of BSL error handling; never execute it."""
    if len(blocks) > 128 or sum(map(len, blocks)) > 65536:
        return False
    root = rule.value.split(".", 1)[0].lower()
    scenarios = (*rule.normal_values, "__OTHER_ERROR_STATUS__")

    # AST nodes are immutable tuples: ("stmt", id, values, syntax) or
    # ("if", ((condition, body), ...), else_body). Each fence is parsed once.
    parsed_fences = []
    for block in blocks:
        values, syntax = bsl_code_views(block)
        if len(syntax) > 65536:
            return False
        statements = []
        start = 0
        depth = 0
        for pos, char in enumerate(syntax):
            if char == "(":
                depth += 1
                if depth > 32: return False
            elif char == ")":
                depth -= 1
                if depth < 0: return False
            elif char == ";" and depth == 0:
                statements.append((values[start:pos].strip(), syntax[start:pos].strip()))
                start = pos + 1
            elif char in "\r\n" and depth == 0:
                # Newlines delimit ordinary statements; header continuation is joined below.
                statements.append((values[start:pos].strip(), syntax[start:pos].strip()))
                start = pos + 1
            if len(statements) > 4096: return False
        if depth: return False
        if values[start:].strip(): statements.append((values[start:].strip(), syntax[start:].strip()))
        # Join multiline parenthesized calls are already retained; join split If headers.
        compact = []
        for original, visible in statements:
            if not visible: continue
            if compact and re.match(r"^(?:И|ИЛИ|AND|OR)\b", visible.strip(), re.I) and re.match(r"^Если\b", compact[-1][1].strip(), re.I):
                a, b = compact.pop(); compact.append((a + " " + original, b + " " + visible))
            elif compact and re.match(r"^(?:Тогда)\b", visible.strip(), re.I) and re.match(r"^Если\b", compact[-1][1].strip(), re.I):
                a, b = compact.pop(); compact.append((a + " " + original, b + " " + visible))
            elif compact and re.match(r"^ВызватьИсключение\s*$", compact[-1][1].strip(), re.I):
                a, b = compact.pop(); compact.append((a + " " + original, b + " " + visible))
            else: compact.append((original, visible))
        index_counter = [0]
        def parse_sequence(i, stops=(), level=0):
            if level > 32:
                raise ValueError
            nodes = []
            while i < len(compact):
                original, visible = compact[i]
                key = visible.strip().split(None, 1)[0].lower() if visible.strip() else ""
                if key in stops: return tuple(nodes), i, key
                if re.match(r"^(?:для|пока|попытка|исключение|перейти|прервать|продолжить|возврат|процедура|функция)\b", visible, re.I):
                    raise ValueError
                if key == "если":
                    branches = []
                    cond = re.match(r"^Если\s+(.+?)\s+Тогда\s*$", original, re.I | re.S)
                    if not cond: raise ValueError
                    body, i, stop = parse_sequence(i + 1, ("иначеесли", "иначе", "конецесли"), level + 1)
                    branches.append((cond.group(1), body))
                    while stop == "иначеесли":
                        cond = re.match(r"^ИначеЕсли\s+(.+?)\s+Тогда\s*$", compact[i][0], re.I | re.S)
                        if not cond: raise ValueError
                        body, i, stop = parse_sequence(i + 1, ("иначеесли", "иначе", "конецесли"), level + 1)
                        branches.append((cond.group(1), body))
                    else_body = ()
                    if stop == "иначе": else_body, i, stop = parse_sequence(i + 1, ("конецесли",), level + 1)
                    if stop != "конецесли": raise ValueError
                    nodes.append(("if", tuple(branches), else_body)); i += 1; continue
                if key in ("иначе", "иначеесли", "конецесли"): raise ValueError
                index_counter[0] += 1
                nodes.append(("stmt", index_counter[0], original, visible)); i += 1
            return tuple(nodes), i, ""
        try:
            tree, end, stop = parse_sequence(0)
            if end != len(compact) or stop: raise ValueError
            parsed_fences.append(tree)
        except (ValueError, RecursionError):
            parsed_fences.append(None)

    def split_expression(expr, pattern):
        """Split only at unquoted top-level operators/argument separators."""
        parts, start, depth, quoted, pos = [], 0, 0, False, 0
        while pos < len(expr):
            char = expr[pos]
            if char == '"':
                if quoted and pos + 1 < len(expr) and expr[pos + 1] == '"':
                    pos += 2
                    continue
                quoted = not quoted
            elif not quoted:
                depth += (char == "(") - (char == ")")
                if depth == 0:
                    match = re.match(pattern, expr[pos:], re.I)
                    if match:
                        parts.append(expr[start:pos])
                        pos += match.end()
                        start = pos
                        continue
            pos += 1
        parts.append(expr[start:])
        return parts

    def interpret(tree, scenario):
        if tree is None: return None
        env = {}
        provenance = set()
        bound = False
        events = []
        def resolve(expr):
            expr = normalize_member_access(expr.strip())
            lit = re.fullmatch(r'"((?:[^"]|"")*)"', expr, re.S)
            if lit: return lit.group(1).replace('""', '"'), False
            if expr.lower() == rule.value.lower() and bound: return scenario, True
            if re.fullmatch(r"[A-Za-z_А-Яа-яЁё][\wА-Яа-яЁё]*", expr):
                name = expr.lower()
                return env.get(name), name in provenance
            pieces = split_expression(expr, r"\+")
            if len(pieces) > 1:
                values = [resolve(x) for x in pieces]
                if all(v[0] is not None for v in values): return "".join(v[0] for v in values), any(v[1] for v in values)
            return None, False
        ops = [0]
        def condition(expr, level=0):
            ops[0] += 1
            if level > 32 or ops[0] > 128: return None
            expr = expr.strip()
            while expr.startswith("(") and expr.endswith(")"):
                dep = 0; enclosed = True
                for p,ch in enumerate(expr):
                    dep += (ch == "(") - (ch == ")")
                    if dep == 0 and p < len(expr)-1: enclosed = False; break
                if not enclosed: break
                expr = expr[1:-1].strip()
            for pattern, is_or in ((r"\s+(?:ИЛИ|OR)\s+", True),
                                   (r"\s+(?:И|AND)\s+", False)):
                pieces = split_expression(expr, pattern)
                if len(pieces) > 1:
                    results = [condition(piece, level + 1) for piece in pieces]
                    if any(result is None for result in results):
                        return None
                    return any(results) if is_or else all(results)
            m = re.match(r"^Не\s+", expr, re.I)
            if m:
                v=condition(expr[m.end():],level+1); return None if v is None else not v
            m = re.fullmatch(r"(ПустаяСтрока|ЗначениеЗаполнено)\s*\((.*)\)", expr, re.I|re.S)
            if m:
                val,prov=resolve(m.group(2))
                if val is None or not prov: return None
                return (val == "") if m.group(1).lower()=="пустаястрока" else (val != "")
            m = re.fullmatch(r"(.+?)\s*(<>|=)\s*(.+)", expr, re.S)
            if m:
                a,ap=resolve(m.group(1)); b,bp=resolve(m.group(3))
                if a is None or b is None or not (ap or bp): return None
                return (a==b) if m.group(2)=="=" else (a!=b)
            return None
        def run(nodes):
            nonlocal bound
            for node in nodes:
                if node[0]=="if":
                    chosen=False
                    for cond,body in node[1]:
                        result=condition(cond)
                        if result is None: return False
                        if result:
                            if not run(body): return False
                            chosen=True; break
                    if not chosen and not run(node[2]): return False
                    continue
                _, ident, original, visible = node
                assign=re.match(r"^([\wА-Яа-яЁё]+(?:\.[\wА-Яа-яЁё]+)*)\s*=\s*(.+)$", original, re.S)
                if assign:
                    lhs,rhs=normalize_member_access(assign.group(1)),assign.group(2).strip()
                    if lhs.lower()==root:
                        bound=False; env.clear(); provenance.clear()
                        call=re.match(r"^([\wА-Яа-яЁё]+(?:\.[\wА-Яа-яЁё]+)*)\s*\(", normalize_member_access(rhs))
                        if call and call.group(1).lower()==rule.source_call.lower(): bound=True; env[root]=scenario
                    elif lhs.lower().startswith(root+"."):
                        bound=False; env.clear(); provenance.clear()
                    else:
                        name=lhs.lower(); val,prov=resolve(rhs); env[name]=val
                        if prov: provenance.add(name)
                        else: provenance.discard(name)
                    continue
                if not bound: continue
                # Effects are identified by exact call head; args may span lines.
                if re.match(r"^ВызватьИсключение\b", visible, re.I):
                    events.append((ident, "raise", scenario not in rule.normal_values, False)); continue
                call=re.match(r"^([\wА-Яа-яЁё]+(?:\.[\wА-Яа-яЁё]+)?)\s*\((.*)\)\s*;?$", visible, re.S)
                if call and call.group(1).lower() in {"сообщить", "записьжурналарегистрации", "общегоназначения.сообщитьпользователю"}:
                    arg=original[original.find("(")+1:original.rfind(")")]
                    # Only supported expressions carry status data, not identifier
                    # words in literals or arbitrary nested function arguments.
                    prov = any(resolve(part)[1] for part in split_expression(arg, r","))
                    events.append((ident,"report",False,bool(prov)))
            return True
        try:
            completed = run(tree)
        except RecursionError:
            return None
        if not completed or not bound: return None
        return events

    for fence_index, tree in enumerate(parsed_fences):
        status_events = [interpret(tree, scenario) for scenario in scenarios]
        if any(events is None for events in status_events):
            continue
        normal_events = status_events[:-1]
        error_events = status_events[-1]
        # A raise in a normal trace invalidates this fence. Provenance-bearing
        # reports are valid anywhere; constant effects require error-only execution.
        if any(any(kind == "raise" for _, kind, _, _ in events) for events in normal_events):
            continue
        valid_normal_locations = {
            ident for events in normal_events for ident, kind, _, _ in events
            if kind == "report"
        }
        proven_error = any(kind == "raise" or (kind == "report" and prov)
                           for _, kind, _, prov in error_events)
        constant_error_only = any(
            ident not in valid_normal_locations and not prov
            for ident, kind, _, prov in error_events
            if kind in ("report", "raise")
        )
        if proven_error or constant_error_only:
            return True
    return False


def score_response(
    case: EvalCase,
    response: str,
    method_index: dict[str, dict[str, MethodInfo]],
    *,
    skill_activated: bool = False,
    require_activation: bool = False,
    reference_read: bool = False,
    require_reference: bool = False,
) -> dict:
    flags = re.I | re.S
    normalized_response = normalize_member_access(response)
    required_hits = [
        bool(re.search(pattern, normalized_response, flags))
        for pattern in case.required_patterns
    ]
    blocks = bsl_blocks(response)
    executable_blocks = executable_bsl_blocks(response)
    code_views = [bsl_code_views(code) for code in executable_blocks]
    bsl_text, bsl_syntax = bsl_code_views("\n".join(executable_blocks))
    required_code_hits = [
        executable_pattern_hit(pattern, bsl_text, bsl_syntax)
        for pattern in case.required_code_patterns
    ]
    # Each block-pattern must be demonstrated in a distinct executable fence.
    # Greedy matching is sufficient because eval patterns describe disjoint steps.
    unmatched_blocks = set(range(len(executable_blocks)))
    required_code_block_hits = []
    for pattern in case.required_code_block_patterns:
        matching_block = next(
            (
                index for index in sorted(unmatched_blocks)
                if executable_pattern_hit(pattern, *code_views[index])
            ),
            None,
        )
        required_code_block_hits.append(matching_block is not None)
        if matching_block is not None:
            unmatched_blocks.remove(matching_block)
    forbidden_hits = [
        pattern for pattern in case.forbidden_patterns + case.forbidden_code_patterns
        if executable_pattern_hit(pattern, bsl_text, bsl_syntax)
    ]
    grounding_patterns = case.activation_patterns or case.required_patterns
    grounding_hits = sum(
        bool(re.search(pattern, normalized_response, flags))
        for pattern in grounding_patterns
    )
    response_grounded = grounding_hits > 0

    calls = []
    invalid_methods = []
    unsafe_calls = []
    for _values, syntax in code_views:
        for match in CALL_RE.finditer(syntax):
            module_name = match.group("module")
            method_name = match.group("method")
            if module_name not in method_index:
                continue
            call = f"{module_name}.{method_name}"
            calls.append(call)
            info = method_index[module_name].get(method_name)
            if info is None:
                invalid_methods.append(call)
                continue
            if module_name.endswith("Переопределяемый") or info.region in SERVICE_REGIONS:
                unsafe_calls.append({"call": call, "region": info.region})

    error_rule_hit = (
        error_handling_rule_satisfied(executable_blocks, case.error_handling_rule)
        if case.error_handling_rule is not None else True
    )
    expected_ok = (
        all(required_hits)
        and all(required_code_hits)
        and all(required_code_block_hits)
        and error_rule_hit
    )
    activation_ok = skill_activated if case.should_trigger else not skill_activated
    reference_ok = reference_read if require_reference else True
    bsl_ok = any(syntax.strip() for _values, syntax in code_views) if case.requires_bsl else True
    quality_passed = (
        bool(response.strip())
        and expected_ok
        and bsl_ok
        and not forbidden_hits
        and not invalid_methods
        and not unsafe_calls
    )
    passed = (
        quality_passed
        and (activation_ok if require_activation else True)
        and reference_ok
    )
    known_calls = len(calls)
    method_accuracy = (
        (known_calls - len(invalid_methods)) / known_calls if known_calls else None
    )
    return {
        "passed": passed,
        "quality_passed": quality_passed,
        "activated": skill_activated,
        "activation_ok": activation_ok,
        "reference_read": reference_read,
        "reference_ok": reference_ok,
        "missing_reference": require_reference and not reference_read,
        "error_handling_rule_passed": error_rule_hit if case.error_handling_rule else None,
        "response_grounded": response_grounded,
        "expected_hits": (
            sum(required_hits) + sum(required_code_hits) + sum(required_code_block_hits)
            + int(case.error_handling_rule is not None and error_rule_hit)
        ),
        "expected_total": (
            len(required_hits) + len(required_code_hits) + len(required_code_block_hits)
            + int(case.error_handling_rule is not None)
        ),
        "expected_score": (
            (sum(required_hits) + sum(required_code_hits) + sum(required_code_block_hits)
             + int(case.error_handling_rule is not None and error_rule_hit))
            / (len(required_hits) + len(required_code_hits) + len(required_code_block_hits)
               + int(case.error_handling_rule is not None))
        ),
        "missing_patterns": [
            pattern for pattern, hit in zip(case.required_patterns, required_hits) if not hit
        ] + [
            pattern for pattern, hit in zip(case.required_code_patterns, required_code_hits)
            if not hit
        ],
        "missing_code_patterns": [
            pattern for pattern, hit in zip(case.required_code_patterns, required_code_hits)
            if not hit
        ] + ([f"error_handling_rule:{case.error_handling_rule.value}"]
             if case.error_handling_rule is not None and not error_rule_hit else []),
        "missing_code_block_patterns": [
            pattern for pattern, hit in zip(
                case.required_code_block_patterns, required_code_block_hits
            ) if not hit
        ],
        "forbidden_hits": forbidden_hits,
        "has_bsl": bool(blocks),
        "known_module_calls": calls,
        "invalid_methods": sorted(set(invalid_methods)),
        "unsafe_calls": unsafe_calls,
        "method_accuracy": method_accuracy,
    }


def resolve_cdx(command: str) -> str:
    path = Path(command)
    if path.is_file():
        return str(path.resolve())
    resolved = shutil.which(command)
    if not resolved:
        raise EvalError(f"Codex launcher not found: {command}")
    return resolved


def find_conflicting_skills(workdir: Path, skill_name: str, target: Path) -> list[Path]:
    conflicts: list[Path] = []
    current = workdir.resolve()
    while True:
        candidate = current / ".agents" / "skills" / skill_name / "SKILL.md"
        if candidate.is_file() and candidate.parent != target.resolve():
            conflicts.append(candidate)
        if current.parent == current:
            break
        current = current.parent
    home_candidate = Path.home() / ".agents" / "skills" / skill_name / "SKILL.md"
    if home_candidate.is_file():
        conflicts.append(home_candidate)
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    legacy = codex_home / "skills" / skill_name / "SKILL.md"
    if legacy.is_file():
        conflicts.append(legacy)
    return sorted(set(path.resolve() for path in conflicts))


@contextmanager
def staged_skill(skill_dir: Path, target: Path) -> Iterator[None]:
    if target.exists():
        raise EvalError(f"Refusing to overwrite existing staged skill: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill_dir, target, ignore=shutil.ignore_patterns(*SKILL_CACHE_PATTERNS))
    try:
        yield
    finally:
        if target.exists():
            shutil.rmtree(target)
        skills_dir = target.parent
        agents_dir = skills_dir.parent
        if skills_dir.is_dir() and not any(skills_dir.iterdir()):
            skills_dir.rmdir()
        if agents_dir.is_dir() and not any(agents_dir.iterdir()):
            agents_dir.rmdir()


def build_cdx_command(
    cdx: str,
    case: EvalCase,
    workdir: Path,
    model: str | None,
    reasoning_effort: str | None,
    *,
    platform_name: str | None = None,
) -> list[str]:
    platform_name = platform_name or os.name
    command = [
        cdx,
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "read-only",
    ]
    if platform_name == "nt":
        # With user config ignored, Codex has no Windows sandbox backend and
        # fails closed by rejecting even read-only shell commands. Select the
        # restricted-token backend explicitly while keeping evals isolated
        # from all other user settings.
        command.extend([
            "-c", 'windows.sandbox="unelevated"',
            "-c", "allow_login_shell=false",
            "-c", 'shell_environment_policy.set.PYTHONIOENCODING="utf-8"',
            "-c", 'shell_environment_policy.set.PYTHONUTF8="1"',
            "-c", "developer_instructions=" + json.dumps(WINDOWS_READING_INSTRUCTIONS),
        ])
    command.extend(["-C", str(workdir)])
    if model:
        command.extend(["--model", model])
    if reasoning_effort:
        command.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])
    command.append(case.task)
    return command


def run_cdx(
    cdx: str,
    case: EvalCase,
    workdir: Path,
    artifact_dir: Path,
    phase: str,
    run_number: int,
    model: str | None,
    reasoning_effort: str | None,
    timeout: int,
    skill_name: str,
) -> dict:
    command = build_cdx_command(cdx, case, workdir, model, reasoning_effort)

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=workdir,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        completed = None
        timed_out = True
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
    elapsed = time.monotonic() - started
    if completed is not None:
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
    else:
        returncode = 124

    prefix = f"{case.id}.{phase}.{run_number}"
    (artifact_dir / f"{prefix}.jsonl").write_text(stdout, encoding="utf-8")
    (artifact_dir / f"{prefix}.stderr.txt").write_text(stderr, encoding="utf-8")
    events, noise = extract_jsonl(stdout)
    response = final_message(events)
    activation_evidence = skill_activation_evidence(events, skill_name)
    reference_evidence = (
        skill_activation_evidence(events, skill_name, case.reference)
        if case.should_trigger and case.reference
        else []
    )
    tool_policy_blocked = "blocked by policy" in stderr
    (artifact_dir / f"{prefix}.response.md").write_text(response, encoding="utf-8")
    return {
        "returncode": returncode,
        "timed_out": timed_out,
        "tool_policy_blocked": tool_policy_blocked,
        "tool_output_decode_errors": tool_output_decode_errors(events),
        "elapsed_seconds": round(elapsed, 3),
        "usage": usage_from_events(events),
        "response": response,
        "skill_activated": bool(activation_evidence),
        "activation_evidence": activation_evidence,
        "expected_reference_read": bool(reference_evidence),
        "reference_evidence": reference_evidence,
        "json_events": len(events),
        "stdout_noise": noise,
        "stderr_tail": stderr[-4000:],
    }


def infrastructure_reason(execution: dict) -> str | None:
    """Return a stable category for failures outside skill-content quality."""
    if execution.get("timed_out"):
        return "timeout"
    if execution.get("tool_policy_blocked"):
        return "sandbox_policy"
    if execution.get("tool_output_decode_errors"):
        return "tool_output_encoding"
    stderr = str(execution.get("stderr_tail", ""))
    if execution.get("returncode", 0) != 0 or not str(execution.get("response", "")).strip():
        for reason, pattern in INFRASTRUCTURE_PATTERNS:
            if pattern.search(stderr):
                return reason
    if execution.get("returncode", 0) != 0:
        return "process_error"
    return None


def execution_status(execution: dict) -> str:
    """Classify one attempted run without conflating quality and infrastructure."""
    if infrastructure_reason(execution) is not None:
        return "infrastructure_failed"
    if not str(execution.get("response", "")).strip():
        return "incomplete"
    score = execution.get("score")
    if not isinstance(score, dict):
        return "incomplete"
    return "completed" if score.get("passed", False) else "quality_failed"


def majority(values: Iterable[bool]) -> bool:
    items = list(values)
    return sum(items) >= (len(items) // 2 + 1)


def resume_run_matrix(
    cases: list[EvalCase], runs: int, stored: dict[str, list[dict | None]] | None
) -> list[list[dict | None]]:
    """Restore durable outcomes; retry missing, incomplete, and infrastructure failures."""
    stored = stored or {}
    matrix: list[list[dict | None]] = []
    for case in cases:
        previous = stored.get(case.id, [])
        case_runs: list[dict | None] = []
        for run_index in range(runs):
            run = previous[run_index] if run_index < len(previous) else None
            if isinstance(run, dict):
                status = run.get("status") or execution_status(run)
                if status in {"completed", "quality_failed"}:
                    case_runs.append(run)
                    continue
            case_runs.append(None)
        matrix.append(case_runs)
    return matrix


def execute_run_matrix(
    cases: list[EvalCase],
    runs: int,
    jobs: int,
    execute: Callable[[EvalCase, int], dict],
    on_run_complete: Callable[[int, int, list[list[dict | None]]], None] | None = None,
    initial_matrix: list[list[dict | None]] | None = None,
) -> list[list[dict]]:
    """Execute missing case runs concurrently and preserve corpus order."""
    matrix = initial_matrix or [[None] * runs for _ in cases]
    if len(matrix) != len(cases) or any(len(case_runs) != runs for case_runs in matrix):
        raise EvalError("Initial run matrix does not match selected cases and --runs")
    pending = [
        (case_index, case, run_number)
        for case_index, case in enumerate(cases)
        for run_number in range(1, runs + 1)
        if matrix[case_index][run_number - 1] is None
    ]
    if pending:
        max_workers = min(jobs, len(pending))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(execute, case, run_number): (case_index, run_number - 1)
                for case_index, case, run_number in pending
            }
            for future in as_completed(futures):
                case_index, run_index = futures[future]
                matrix[case_index][run_index] = future.result()
                if on_run_complete:
                    on_run_complete(case_index, run_index, matrix)
    return [[run for run in case_runs if run is not None] for case_runs in matrix]


def phase_case_records(
    cases: list[EvalCase], run_matrix: list[list[dict | None]], expected_runs: int
) -> list[dict]:
    """Build ordered report records for cases whose runs are complete."""
    records = []
    for case, raw_runs in zip(cases, run_matrix):
        if len(raw_runs) != expected_runs or any(run is None for run in raw_runs):
            continue
        case_runs = [run for run in raw_runs if run is not None]
        complete = all(
            run.get("status", "completed") in {"completed", "quality_failed"}
            for run in case_runs
        )
        records.append({
            "id": case.id,
            "reference": case.reference,
            "should_trigger": case.should_trigger,
            "complete": complete,
            "majority_passed": (
                majority(run["score"]["passed"] for run in case_runs) if complete else None
            ),
            "majority_activated": (
                majority(run["skill_activated"] for run in case_runs) if complete else None
            ),
            "majority_reference_read": (
                majority(run.get("expected_reference_read", False) for run in case_runs)
                if complete and case.should_trigger and case.reference else None
            ),
            "runs": case_runs,
        })
    return records


def summarize_phase(cases: list[dict]) -> dict:
    completed_cases = [case for case in cases if case.get("complete", True)]
    passed_cases = sum(case["majority_passed"] for case in completed_cases)
    trigger_cases = [case for case in completed_cases if case["should_trigger"]]
    activated_cases = sum(case["majority_activated"] for case in trigger_cases)
    reference_cases = [case for case in trigger_cases if case.get("reference")]
    reference_read_cases = sum(
        bool(case.get("majority_reference_read")) for case in reference_cases
    )
    runs = [run for case in cases for run in case["runs"]]
    input_tokens = [run["usage"].get("input_tokens", 0) for run in runs]
    output_tokens = [run["usage"].get("output_tokens", 0) for run in runs]
    statuses = [run.get("status") or execution_status(run) for run in runs]
    infrastructure_reasons: dict[str, int] = {}
    for run, status in zip(runs, statuses):
        if status != "infrastructure_failed":
            continue
        reason = run.get("infrastructure_reason") or infrastructure_reason(run) or "unknown"
        infrastructure_reasons[reason] = infrastructure_reasons.get(reason, 0) + 1
    return {
        "cases": len(completed_cases),
        "attempted_cases": len(cases),
        "incomplete_cases": len(cases) - len(completed_cases),
        "passed_cases": passed_cases,
        "pass_rate": passed_cases / len(completed_cases) if completed_cases else 0.0,
        "trigger_cases": len(trigger_cases),
        "activated_cases": activated_cases,
        "activation_rate": activated_cases / len(trigger_cases) if trigger_cases else 1.0,
        "reference_cases": len(reference_cases),
        "reference_read_cases": reference_read_cases,
        "reference_read_rate": (
            reference_read_cases / len(reference_cases) if reference_cases else 1.0
        ),
        "invalid_methods": sum(len(run["score"]["invalid_methods"]) for run in runs),
        "unsafe_calls": sum(len(run["score"]["unsafe_calls"]) for run in runs),
        "forbidden_hits": sum(len(run["score"]["forbidden_hits"]) for run in runs),
        "failed_processes": sum(
            run["returncode"] != 0 or run.get("tool_policy_blocked", False)
            for run in runs
        ),
        "tool_policy_blocks": sum(
            run.get("tool_policy_blocked", False) for run in runs
        ),
        "infrastructure_failures": statuses.count("infrastructure_failed"),
        "infrastructure_reasons": infrastructure_reasons,
        "incomplete_runs": statuses.count("incomplete"),
        "quality_failures": statuses.count("quality_failed"),
        "input_tokens": sum(input_tokens),
        "output_tokens": sum(output_tokens),
    }


def atomic_write_json(path: Path, payload: dict) -> None:
    """Atomically replace a JSON report so interruption cannot leave a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def validate_resume_report(report: dict, expected: dict) -> None:
    """Reject resume requests that could mix incomparable evaluation results."""
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise EvalError(f"--resume requires a schema_version={REPORT_SCHEMA_VERSION} report")
    for key, expected_value in expected.items():
        if report.get(key) != expected_value:
            raise EvalError(
                f"Cannot resume: report {key}={report.get(key)!r}, "
                f"requested {expected_value!r}"
            )


def green_gate_reasons(
    summary: dict, min_pass_rate: float, min_activation_rate: float
) -> list[str]:
    """Apply GREEN quality gates, including exact reference-read coverage."""
    reasons = []
    if summary["pass_rate"] < min_pass_rate:
        reasons.append(
            f"pass_rate {summary['pass_rate']:.1%} < {min_pass_rate:.1%}"
        )
    if summary["activation_rate"] < min_activation_rate:
        reasons.append(
            f"activation_rate {summary['activation_rate']:.1%} < "
            f"{min_activation_rate:.1%}"
        )
    if summary["reference_cases"] and summary["reference_read_rate"] < 1.0:
        reasons.append(
            "reference_read_rate must be 100%, got "
            f"{summary['reference_read_rate']:.1%}"
        )
    for metric in ("invalid_methods", "unsafe_calls", "forbidden_hits", "failed_processes"):
        if summary[metric]:
            reasons.append(f"{metric} must be 0, got {summary[metric]}")
    return reasons


def print_summary(report: dict) -> None:
    print("\n--- BSP skill behavioral evaluation ---")
    print(f"Cases: {len(report['selected_cases'])}; runs per phase: {report['runs']}")
    for phase in ("red", "green"):
        if phase not in report["phases"]:
            continue
        summary = report["phases"][phase]["summary"]
        print(
            f"{phase.upper():5} pass={summary['passed_cases']}/{summary['cases']} "
            f"activation={summary['activated_cases']}/{summary['trigger_cases']} "
            f"reference-read={summary['reference_read_cases']}/{summary['reference_cases']} "
            f"invalid={summary['invalid_methods']} unsafe={summary['unsafe_calls']} "
            f"forbidden={summary['forbidden_hits']} "
            f"failed={summary['failed_processes']} "
            f"infra={summary['infrastructure_failures']} "
            f"incomplete={summary['incomplete_runs']} "
            f"policy-blocked={summary['tool_policy_blocks']} tokens="
            f"{summary['input_tokens'] + summary['output_tokens']}"
        )
    if "green" in report["phases"]:
        print(f"GREEN gate: {'PASS' if report['gate']['passed'] else 'FAIL'}")
        for reason in report["gate"]["reasons"]:
            print(f"  - {reason}")
    print(f"Report: {report['report_path']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RED/GREEN evaluations for the BSP skill")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument(
        "--reference-matrix", default=str(DEFAULT_REFERENCE_MATRIX),
        help="Checked reference -> eval cases manifest",
    )
    parser.add_argument("--case", action="append", dest="case_ids", help="Run one case id; repeatable")
    parser.add_argument("--skill", default=str(DEFAULT_SKILL), help="Path to the skill directory")
    parser.add_argument("--dir", default=str(DEFAULT_WORKDIR), help="Codex working directory")
    parser.add_argument("--bsl-src", default=str(DEFAULT_BSL_SRC), help="Configuration root with CommonModules")
    parser.add_argument("--cdx", default="cdx", help="Codex launcher command (default: cdx)")
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Exact model id (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--reasoning-effort", choices=("low", "medium", "high", "xhigh"),
        help="Optional model_reasoning_effort override",
    )
    parser.add_argument("--runs", type=int, default=3, help="Runs per case and phase")
    parser.add_argument(
        "--jobs", type=int, default=6,
        help="Maximum concurrent cdx invocations (default: 6)",
    )
    parser.add_argument("--phase", choices=("red", "green", "both"), default="both")
    parser.add_argument("--timeout", type=int, default=600, help="Seconds per cdx invocation")
    parser.add_argument("--output", help="Report JSON path; artifacts are stored beside it")
    parser.add_argument(
        "--resume", action="store_true",
        help="Continue --output report; retry only missing/infrastructure/incomplete runs",
    )
    parser.add_argument("--min-pass-rate", type=float, default=0.80)
    parser.add_argument("--min-activation-rate", type=float, default=0.80)
    parser.add_argument("--dry-run", action="store_true", help="Validate setup without model calls")
    parser.add_argument("--no-fail", action="store_true", help="Always return zero after completed runs")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.runs < 1:
            raise EvalError("--runs must be at least 1")
        if args.jobs < 1:
            raise EvalError("--jobs must be at least 1")
        for name, value in (
            ("--min-pass-rate", args.min_pass_rate),
            ("--min-activation-rate", args.min_activation_rate),
        ):
            if not 0 <= value <= 1:
                raise EvalError(f"{name} must be between 0 and 1")

        cases_path = Path(args.cases).resolve()
        cases = load_cases(cases_path)
        matrix_path = Path(args.reference_matrix).resolve()
        reference_matrix, unscoped_cases = load_reference_matrix(matrix_path)
        validate_reference_matrix(
            cases,
            reference_matrix,
            unscoped_cases,
            Path(args.skill).resolve() / "references",
        )
        if args.case_ids:
            requested = set(args.case_ids)
            known = {case.id for case in cases}
            missing = sorted(requested - known)
            if missing:
                raise EvalError(f"Unknown case id(s): {', '.join(missing)}")
            cases = [case for case in cases if case.id in requested]
        skill_dir = Path(args.skill).resolve()
        workdir = Path(args.dir).resolve()
        bsl_src = Path(args.bsl_src).resolve() if args.bsl_src else None
        skill_name = validate_skill(skill_dir)
        if not workdir.is_dir():
            raise EvalError(f"Working directory not found: {workdir}")
        method_index = load_method_index(skill_dir, bsl_src)
        cdx = resolve_cdx(args.cdx)
        stage_target = workdir / ".agents" / "skills" / skill_name
        conflicts = find_conflicting_skills(workdir, skill_name, stage_target)
        if conflicts:
            joined = "\n  ".join(str(path) for path in conflicts)
            raise EvalError(
                "A BSP skill is already discoverable and would contaminate RED:\n  " + joined
            )

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if args.resume and not args.output:
            raise EvalError("--resume requires --output <existing-report.json>")
        if args.output:
            report_path = Path(args.output).resolve()
            artifact_dir = report_path.parent / f"{report_path.stem}-artifacts"
        else:
            artifact_dir = REPO_ROOT / ".tmp" / "bsp-evals" / timestamp
            report_path = artifact_dir / "report.json"

        phases = ["red", "green"] if args.phase == "both" else [args.phase]
        report_settings = {
            "launcher": cdx,
            "model": args.model,
            "reasoning_effort": args.reasoning_effort,
            "skill": str(skill_dir),
            "workdir": str(workdir),
            "bsl_src": str(bsl_src) if bsl_src else None,
            "selected_cases": [case.id for case in cases],
            "corpus_sha256": file_sha256(cases_path),
            "reference_matrix_sha256": file_sha256(matrix_path),
            "skill_sha256": skill_sha256(skill_dir),
            "runner_sha256": file_sha256(Path(__file__)),
            "runs": args.runs,
            "phases_requested": phases,
            "min_pass_rate": args.min_pass_rate,
            "min_activation_rate": args.min_activation_rate,
        }

        if args.dry_run:
            covered_references = sum(bool(case_ids) for case_ids in reference_matrix.values())
            print(f"PASS: {len(cases)} eval cases are valid.")
            print(
                f"Reference matrix: {covered_references}/{len(reference_matrix)} "
                "references have eval cases"
            )
            print(f"Skill: {skill_dir} ({skill_name})")
            print(f"Workdir: {workdir}")
            print(f"BSL modules indexed: {len(method_index)}")
            print(f"Launcher: {cdx}")
            print(f"Model: {args.model}")
            print(f"GREEN staging target: {stage_target}")
            return

        if args.resume:
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise EvalError(f"Cannot read resume report {report_path}: {exc}") from exc
            validate_resume_report(report, report_settings)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            report["complete"] = False
            report["resumed_at"] = datetime.now(timezone.utc).isoformat()
            report["jobs"] = args.jobs
        else:
            artifact_dir.mkdir(parents=True, exist_ok=False)
            report = {
                "schema_version": REPORT_SCHEMA_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                **report_settings,
                "jobs": args.jobs,
                "complete": False,
                "phases": {},
                "report_path": str(report_path),
            }

        for phase in phases:
            context = staged_skill(skill_dir, stage_target) if phase == "green" else _null_context()
            with context:
                def execute(case: EvalCase, run_number: int) -> dict:
                    print(
                        f"[{phase.upper()}] {case.id} run {run_number}/{args.runs}",
                        flush=True,
                    )
                    execution = run_cdx(
                        cdx, case, workdir, artifact_dir, phase, run_number,
                        args.model, args.reasoning_effort, args.timeout, skill_name,
                    )
                    execution["score"] = score_response(
                        case,
                        execution["response"],
                        method_index,
                        skill_activated=execution["skill_activated"],
                        require_activation=phase == "green",
                        reference_read=execution["expected_reference_read"],
                        require_reference=(
                            phase == "green" and case.should_trigger and bool(case.reference)
                        ),
                    )
                    execution["infrastructure_reason"] = infrastructure_reason(execution)
                    execution["status"] = execution_status(execution)
                    return execution

                def save_progress(
                    _case_index: int,
                    _run_index: int,
                    matrix: list[list[dict | None]],
                ) -> None:
                    phase_cases = phase_case_records(cases, matrix, args.runs)
                    report["phases"][phase] = {
                        "run_matrix": {
                            case.id: matrix[index] for index, case in enumerate(cases)
                        },
                        "cases": phase_cases,
                        "summary": summarize_phase(phase_cases),
                    }
                    atomic_write_json(report_path, report)

                stored_runs = report.get("phases", {}).get(phase, {}).get("run_matrix")
                initial_matrix = resume_run_matrix(cases, args.runs, stored_runs)
                run_matrix = execute_run_matrix(
                    cases, args.runs, args.jobs, execute,
                    on_run_complete=save_progress,
                    initial_matrix=initial_matrix,
                )
                phase_cases = phase_case_records(cases, run_matrix, args.runs)
            report["phases"][phase] = {
                "run_matrix": {
                    case.id: run_matrix[index] for index, case in enumerate(cases)
                },
                "cases": phase_cases,
                "summary": summarize_phase(phase_cases),
            }
            atomic_write_json(report_path, report)

        gate_reasons = []
        if "green" in report["phases"]:
            green = report["phases"]["green"]["summary"]
            gate_reasons.extend(green_gate_reasons(
                green, args.min_pass_rate, args.min_activation_rate
            ))
        retryable_runs = [
            run
            for phase in phases
            for runs_by_case in report["phases"][phase]["run_matrix"].values()
            for run in runs_by_case
            if run is None or run.get("status") in {"infrastructure_failed", "incomplete"}
        ]
        if retryable_runs:
            gate_reasons.append(
                f"{len(retryable_runs)} run(s) incomplete or infrastructure-failed; use --resume"
            )
        report["gate"] = {"passed": not gate_reasons, "reasons": gate_reasons}
        report["complete"] = not retryable_runs
        atomic_write_json(report_path, report)
        print_summary(report)
        if not args.no_fail and not report["gate"]["passed"]:
            sys.exit(1)
    except EvalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)


@contextmanager
def _null_context() -> Iterator[None]:
    yield


if __name__ == "__main__":
    main()
