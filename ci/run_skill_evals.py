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
import hashlib
import importlib.util
import json
import os
import re
import shutil
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
DEFAULT_SKILL = REPO_ROOT / "skills" / "bsp"
DEFAULT_WORKDIR = REPO_ROOT / "src"
DEFAULT_BSL_SRC = REPO_ROOT / "src" / "cf"
DEFAULT_MODEL = "gpt-5.6-luna"
SERVICE_REGIONS = frozenset({
    "СлужебныйПрограммныйИнтерфейс",
    "СлужебныеПроцедурыИФункции",
    "УстаревшиеПроцедурыИФункции",
})
CALL_RE = re.compile(
    r"(?<![\w.])(?P<module>[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_]*)\s*\.\s*"
    r"(?P<method>[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)\s*\("
)
BSL_FENCE_RE = re.compile(r"```(?:bsl|1c)?\s*\n(?P<code>.*?)```", re.I | re.S)
NEGATIVE_BLOCK_RE = re.compile(
    r"(?:не\s+(?:следует|вызыва|существ|нужно|запуска|команд|долж|явля|подход)|"
    r"(?:публичн|метод|модул|вызов)[^.\n]{0,120}\bнет\b|нельзя|"
    r"неправиль|ошибочн|невер|ложн|"
    r"антипаттерн|запрещ)",
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
        for pattern in required + forbidden + activation:
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
        ))
    if not result:
        raise EvalError("Eval corpus is empty")
    return result


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
    for path in sorted(item for item in skill_dir.rglob("*") if item.is_file()):
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


def skill_activation_evidence(events: Iterable[dict], skill_name: str) -> list[str]:
    """Return observable commands that read the staged project skill."""
    marker = f"/.agents/skills/{skill_name.lower()}/"
    evidence = []
    for event in events:
        if event.get("type") not in {"item.started", "item.completed"}:
            continue
        item = event.get("item") or {}
        if item.get("type") != "command_execution":
            continue
        command = str(item.get("command", ""))
        normalized = re.sub(r"/+", "/", command.replace("\\", "/").lower())
        if marker in normalized and (
            "skill.md" in normalized or f"{marker}references/" in normalized
        ):
            if command not in evidence:
                evidence.append(command)
    return evidence


def bsl_blocks(response: str) -> list[str]:
    blocks = [match.group("code") for match in BSL_FENCE_RE.finditer(response)]
    if blocks:
        return blocks
    if re.search(r"\b(?:Процедура|Функция)\b", response, re.I):
        return [response]
    return []


def executable_bsl_blocks(response: str) -> list[str]:
    """Exclude fenced snippets explicitly presented as incorrect examples."""
    matches = list(BSL_FENCE_RE.finditer(response))
    if not matches:
        return bsl_blocks(response)
    negative = []
    for match in matches:
        prefix = response[max(0, match.start() - 240):match.start()]
        immediate_prefix = re.split(r"\n\s*\n", prefix.rstrip())[-1]
        suffix = response[match.end():match.end() + 320]
        immediate_suffix = re.split(r"\n\s*\n", suffix.lstrip())[0]
        code = match.group("code")
        first_lines = "\n".join(code.splitlines()[:3])
        negative.append(bool(
            NEGATIVE_BLOCK_RE.search(immediate_prefix)
            or NEGATIVE_BLOCK_RE.search(immediate_suffix)
            or NEGATIVE_BLOCK_RE.search(first_lines)
        ))

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
    return re.sub(
        r"(?<=[A-Za-zА-Яа-яЁё0-9_])\s*\.\s*(?=[A-Za-zА-Яа-яЁё_])",
        ".",
        text,
    )


def score_response(
    case: EvalCase,
    response: str,
    method_index: dict[str, dict[str, MethodInfo]],
    *,
    skill_activated: bool = False,
    require_activation: bool = False,
) -> dict:
    flags = re.I | re.S
    normalized_response = normalize_member_access(response)
    required_hits = [
        bool(re.search(pattern, normalized_response, flags))
        for pattern in case.required_patterns
    ]
    blocks = bsl_blocks(response)
    executable_blocks = executable_bsl_blocks(response)
    bsl_text = normalize_member_access("\n".join(executable_blocks))
    forbidden_hits = [
        pattern for pattern in case.forbidden_patterns if re.search(pattern, bsl_text, flags)
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
    for code in executable_blocks:
        for match in CALL_RE.finditer(code):
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

    expected_ok = all(required_hits)
    activation_ok = skill_activated if case.should_trigger else not skill_activated
    bsl_ok = bool(blocks) if case.requires_bsl else True
    quality_passed = (
        bool(response.strip())
        and expected_ok
        and bsl_ok
        and not forbidden_hits
        and not invalid_methods
        and not unsafe_calls
    )
    passed = quality_passed and (activation_ok if require_activation else True)
    known_calls = len(calls)
    method_accuracy = (
        (known_calls - len(invalid_methods)) / known_calls if known_calls else None
    )
    return {
        "passed": passed,
        "quality_passed": quality_passed,
        "activated": skill_activated,
        "activation_ok": activation_ok,
        "response_grounded": response_grounded,
        "expected_hits": sum(required_hits),
        "expected_total": len(required_hits),
        "expected_score": sum(required_hits) / len(required_hits),
        "missing_patterns": [
            pattern for pattern, hit in zip(case.required_patterns, required_hits) if not hit
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
    shutil.copytree(skill_dir, target)
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
        command.extend(["-c", 'windows.sandbox="unelevated"'])
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
    tool_policy_blocked = "blocked by policy" in stderr
    (artifact_dir / f"{prefix}.response.md").write_text(response, encoding="utf-8")
    return {
        "returncode": returncode,
        "timed_out": timed_out,
        "tool_policy_blocked": tool_policy_blocked,
        "elapsed_seconds": round(elapsed, 3),
        "usage": usage_from_events(events),
        "response": response,
        "skill_activated": bool(activation_evidence),
        "activation_evidence": activation_evidence,
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
            "runs": case_runs,
        })
    return records


def summarize_phase(cases: list[dict]) -> dict:
    completed_cases = [case for case in cases if case.get("complete", True)]
    passed_cases = sum(case["majority_passed"] for case in completed_cases)
    trigger_cases = [case for case in completed_cases if case["should_trigger"]]
    activated_cases = sum(case["majority_activated"] for case in trigger_cases)
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
    if report.get("schema_version") != 2:
        raise EvalError("--resume requires a schema_version=2 report")
    for key, expected_value in expected.items():
        if report.get(key) != expected_value:
            raise EvalError(
                f"Cannot resume: report {key}={report.get(key)!r}, "
                f"requested {expected_value!r}"
            )


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
            "skill_sha256": skill_sha256(skill_dir),
            "runs": args.runs,
            "phases_requested": phases,
            "min_pass_rate": args.min_pass_rate,
            "min_activation_rate": args.min_activation_rate,
        }

        if args.dry_run:
            print(f"PASS: {len(cases)} eval cases are valid.")
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
                "schema_version": 2,
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
            if green["pass_rate"] < args.min_pass_rate:
                gate_reasons.append(
                    f"pass_rate {green['pass_rate']:.1%} < {args.min_pass_rate:.1%}"
                )
            if green["activation_rate"] < args.min_activation_rate:
                gate_reasons.append(
                    f"activation_rate {green['activation_rate']:.1%} < "
                    f"{args.min_activation_rate:.1%}"
                )
            for metric in ("invalid_methods", "unsafe_calls", "forbidden_hits", "failed_processes"):
                if green[metric]:
                    gate_reasons.append(f"{metric} must be 0, got {green[metric]}")
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
