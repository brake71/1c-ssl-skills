import hashlib
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "ci" / "run_skill_evals.py"
SKILL_DIR = REPO_ROOT / "skills" / "bsp"
FIXTURE_SRC = REPO_ROOT / "tests" / "fixtures" / "cf"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = load_module(RUNNER_PATH, "run_skill_evals_for_tests")


class EvalCorpusTests(unittest.TestCase):
    def test_repository_corpus_is_valid(self):
        cases = runner.load_cases(REPO_ROOT / "evals" / "cases.json")
        self.assertGreaterEqual(len(cases), 12)
        self.assertTrue(any(not case.should_trigger for case in cases))
        self.assertEqual(len(cases), len({case.id for case in cases}))

    def test_repository_reference_matrix_matches_corpus_and_skill(self):
        cases = runner.load_cases(REPO_ROOT / "evals" / "cases.json")
        references, unscoped = runner.load_reference_matrix(
            REPO_ROOT / "evals" / "reference-matrix.json"
        )
        matrix = runner.validate_reference_matrix(
            cases, references, unscoped, SKILL_DIR / "references"
        )
        self.assertEqual(len(matrix), 24)
        self.assertEqual(
            matrix["longs-and-jobs.md"],
            [
                "long-operation-with-result",
                "scheduled-job-module-suffix",
                "nonexistent-service-module",
            ],
        )
        self.assertEqual(unscoped, ["plain-bsl-no-bsp"])

    def test_reference_matrix_rejects_missing_reference_and_unassigned_case(self):
        cases = runner.load_cases(REPO_ROOT / "evals" / "cases.json")
        references, unscoped = runner.load_reference_matrix(
            REPO_ROOT / "evals" / "reference-matrix.json"
        )
        references.pop("admin-tools.md")
        with self.assertRaisesRegex(runner.EvalError, "matrix is missing"):
            runner.validate_reference_matrix(
                cases, references, unscoped, SKILL_DIR / "references"
            )

        references["admin-tools.md"] = []
        references["base-common.md"].remove("message-bound-to-field")
        with self.assertRaisesRegex(runner.EvalError, "does not assign"):
            runner.validate_reference_matrix(
                cases, references, unscoped, SKILL_DIR / "references"
            )

    def test_new_code_pattern_fields_are_loaded_and_regex_validated(self):
        payload = {
            "version": 1,
            "cases": [{
                **self._raw_case("code-patterns"),
                "required_code_patterns": [r"Вызов\(\)"],
                "required_code_block_patterns": [r"Процедура А", r"Процедура Б"],
                "forbidden_code_patterns": [r"Запрещённый\("],
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            case = runner.load_cases(path)[0]
            self.assertEqual(case.required_code_patterns, (r"Вызов\(\)",))
            self.assertEqual(
                case.required_code_block_patterns, (r"Процедура А", r"Процедура Б")
            )
            self.assertEqual(case.forbidden_code_patterns, (r"Запрещённый\(",))

            payload["cases"][0]["required_code_patterns"] = ["["]
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(runner.EvalError, "Invalid regex"):
                runner.load_cases(path)

    def test_error_handling_rule_is_optional_and_configuration_is_validated(self):
        payload = {"version": 1, "cases": [self._raw_case("rule-case")]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIsNone(runner.load_cases(path)[0].error_handling_rule)
            payload["cases"][0]["error_handling_rule"] = {
                "value": "Результат.КодОшибки", "source_call": "Модуль.Метод", "normal_values": []
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(runner.EvalError, "invalid error_handling_rule"):
                runner.load_cases(path)

    def test_duplicate_case_id_is_rejected(self):
        payload = {
            "version": 1,
            "cases": [self._raw_case("same"), self._raw_case("same")],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(runner.EvalError, "Duplicate"):
                runner.load_cases(path)

    @staticmethod
    def _raw_case(case_id):
        return {
            "id": case_id,
            "task": "Задача",
            "required_patterns": ["Ожидается"],
            "forbidden_patterns": [],
        }


class JsonlTests(unittest.TestCase):
    def test_proxy_noise_is_ignored_and_final_message_is_extracted(self):
        text = "\n".join([
            "Запуск Codex с прокси",
            '{"type":"thread.started","thread_id":"1"}',
            '{"type":"item.completed","item":{"type":"agent_message","text":"Ответ"}}',
            '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}',
        ])
        events, noise = runner.extract_jsonl(text)
        self.assertEqual(noise, ["Запуск Codex с прокси"])
        self.assertEqual(runner.final_message(events), "Ответ")
        self.assertEqual(runner.usage_from_events(events)["input_tokens"], 10)

    def test_skill_activation_uses_observable_staged_skill_read(self):
        events = [{
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "Get-Content C:\\repo\\.agents\\skills\\bsp\\SKILL.md",
            },
        }]
        events[0]["item"]["aggregated_output"] = "# Применение БСП\nПравила и примеры."
        evidence = runner.skill_activation_evidence(events, "bsp")
        self.assertEqual(len(evidence), 1)

    def test_reference_read_is_required_for_scoped_case_and_path_must_match_exactly(self):
        skill_read = [{
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "Get-Content C:\\repo\\.agents\\skills\\bsp\\SKILL.md",
            },
        }]
        correct_relative_reference = [{
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "Get-Content -Encoding utf8 '.agents/skills/bsp/references/prefixes.md'",
            },
        }]
        correct_absolute_reference = [{
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "Get-Content C:\\repo\\.agents\\skills\\bsp\\references\\prefixes.md -Raw",
            },
        }]
        wrong_reference = [{
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "Get-Content '.agents/skills/bsp/references/print-reports.md'",
            },
        }]
        similarly_named_file = [{
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "Get-Content '.agents/skills/bsp/references/prefixes.md.bak'",
            },
        }]
        non_read_command = [{
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "Write-Output '.agents/skills/bsp/references/prefixes.md'",
            },
        }]
        incomplete_read = [{
            "type": "item.started",
            "item": {
                "type": "command_execution",
                "command": "Get-Content '.agents/skills/bsp/references/prefixes.md'",
            },
        }]
        failed_read = [{
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "Get-Content '.agents/skills/bsp/references/prefixes.md'",
                "exit_code": 1,
            },
        }]

        for items in (skill_read, correct_relative_reference, correct_absolute_reference,
                      wrong_reference, similarly_named_file, non_read_command,
                      incomplete_read, failed_read):
            items[0]["item"]["aggregated_output"] = "# Сценарий\nПравила и BSL-пример."
        self.assertEqual(len(runner.skill_activation_evidence(skill_read, "bsp")), 1)
        self.assertEqual(
            runner.skill_activation_evidence(skill_read, "bsp", reference="prefixes.md"),
            [],
        )
        self.assertEqual(
            len(runner.skill_activation_evidence(
                correct_relative_reference, "bsp", reference="prefixes.md"
            )),
            1,
        )
        self.assertEqual(
            len(runner.skill_activation_evidence(
                correct_absolute_reference, "bsp", reference="prefixes.md"
            )),
            1,
        )
        self.assertEqual(
            runner.skill_activation_evidence(
                wrong_reference, "bsp", reference="prefixes.md"
            ),
            [],
        )
        self.assertEqual(
            runner.skill_activation_evidence(
                similarly_named_file, "bsp", reference="prefixes.md"
            ),
            [],
        )
        self.assertEqual(
            runner.skill_activation_evidence(
                non_read_command, "bsp", reference="prefixes.md"
            ),
            [],
        )
        self.assertEqual(
            runner.skill_activation_evidence(
                incomplete_read, "bsp", reference="prefixes.md"
            ),
            [],
        )
        self.assertEqual(
            runner.skill_activation_evidence(
                failed_read, "bsp", reference="prefixes.md"
            ),
            [],
        )
        self.assertEqual(
            len(runner.skill_activation_evidence(correct_relative_reference, "bsp")),
            1,
        )

    def test_file_listing_count_and_empty_output_do_not_prove_reference_read(self):
        path = ".agents/skills/bsp/references/prefixes.md"
        for command in (f"rg --files {path}", f"rg -l Префикс {path}",
                        f"rg --files-with-matches Префикс {path}",
                        f"rg -c Префикс {path}", f"grep -l Префикс {path}"):
            with self.subTest(command=command):
                events = [{"type": "item.completed", "item": {
                    "type": "command_execution", "exit_code": 0,
                    "command": command, "aggregated_output": path,
                }}]
                self.assertEqual(runner.skill_activation_evidence(events, "bsp", "prefixes.md"), [])
        events[0]["item"].update(command=f"rg -n Префикс {path}", aggregated_output="")
        self.assertEqual(runner.skill_activation_evidence(events, "bsp", "prefixes.md"), [])

    def test_read_command_and_reference_must_be_in_same_shell_segment(self):
        path = ".agents/skills/bsp/references/prefixes.md"
        events = [{"type": "item.completed", "item": {
            "type": "command_execution", "exit_code": 0,
            "command": f"rg -n rule README.md; echo {path}",
            "aggregated_output": f"1:rule\n{path}",
        }}]
        self.assertEqual(runner.skill_activation_evidence(events, "bsp", "prefixes.md"), [])
        events[0]["item"].update(
            command=f"rg --files; Get-Content {path}",
            aggregated_output="# Префиксы\nСценарий реализации.",
        )
        self.assertEqual(len(runner.skill_activation_evidence(events, "bsp", "prefixes.md")), 1)

    def test_rg_pattern_operand_is_not_a_read_target(self):
        path = ".agents/skills/bsp/references/prefixes.md"
        for command in (f"rg -n -- {path} README.md",
                        f"rg -n -g '*.md' {path} README.md",
                        f"rg -n -e {path} README.md"):
            events = [{"type": "item.completed", "item": {
                "type": "command_execution", "exit_code": 0,
                "command": command, "aggregated_output": f"README.md:1:{path}",
            }}]
            self.assertEqual(runner.skill_activation_evidence(events, "bsp", "prefixes.md"), [])
        for command in (f"rg -n -C 3 Префикс {path}",
                        f"rg -n -e Префикс -- {path}",
                        f"rg -n -g '*.md' Префикс {path}"):
            events[0]["item"]["command"] = command
            self.assertEqual(len(runner.skill_activation_evidence(events, "bsp", "prefixes.md")), 1)

    def test_python_inline_reader_is_observable_but_a_filename_print_is_not(self):
        path = ".agents/skills/bsp/references/prefixes.md"
        programs = (
            f"print(open('{path}', encoding='utf-8').read())",
            f"from pathlib import Path; print(Path('{path}').read_text(encoding='utf-8'))",
        )
        for program in programs:
            direct = f'python -c "{program}"'
            wrapped = 'pwsh -NoProfile -Command ' + json.dumps(direct)
            for command in (direct, wrapped):
                events = [{"type": "item.completed", "item": {
                    "type": "command_execution", "exit_code": 0,
                    "command": command, "aggregated_output": "# Префиксы\nСценарий реализации.",
                }}]
                self.assertEqual(len(runner.skill_activation_evidence(events, "bsp", "prefixes.md")), 1)
        events[0]["item"]["command"] = f'python -c "print(\'{path}\')"'
        self.assertEqual(runner.skill_activation_evidence(events, "bsp", "prefixes.md"), [])

    def test_python_path_text_and_selected_lines_are_observable(self):
        path = r".agents/skills/bsp/references/multilang hook.md"
        windows_path = r".agents\skills\bsp\references\multilang hook.md"
        code = f"from pathlib import Path; p=Path({windows_path!r}); print(p.read_text())"
        self.assertEqual(runner.python_reader_targets(["python", "-c", code]), [windows_path])
        programs = (
            "from pathlib import Path; p=Path(" + repr(path) + "); print(p.read_text(encoding='utf-8'))",
            "from pathlib import Path; p=Path(" + repr(path) + "); t=p.read_text(encoding='utf-8').splitlines(); print('\\n'.join(f'{i+1}: {t[i]}' for i in range(346, 380)))",
            "from pathlib import Path; p=Path(" + repr(path) + "); t=p.read_text(encoding='utf-8').splitlines(); print('\\n'.join(f'{i}: {line}' for i, line in enumerate(t)))",
            "from pathlib import Path; p=Path(" + repr(path) + "); t=p.read_text(encoding='utf-8').splitlines(); print(t[346:380])",
        )
        for program in programs:
            with self.subTest(program=program):
                events = [{"type": "item.completed", "item": {
                    "type": "command_execution", "exit_code": 0,
                    "command": f'python -c "{program}"', "aggregated_output": "actual file content",
                }}]
                self.assertEqual(len(runner.skill_activation_evidence(events, "bsp", "multilang hook.md")), 1)

    def test_python_reader_rejects_non_observable_or_conditional_reads(self):
        path = ".agents/skills/bsp/references/prefixes.md"
        programs = (
            f"from pathlib import Path; p=Path('{path}'); print(p)",
            f"from pathlib import Path; p=Path('{path}'); t=p.read_text(); print('filename')",
            f"from pathlib import Path; p=Path('{path}'); t=p.read_text(); t='literal'; print(t)",
            f"open = lambda name: type('F', (), {{'read': lambda self: 'fake'}})(); t = open('{path}').read(); print(t)",
            f"from pathlib import Path; p=Path('{path}'); print(p.read_text(), file=open('/tmp/out','w'))",
            f"print = lambda value: None; print(open('{path}').read())",
            f"from pathlib import Path; p=Path('{path}'); print(p.read_text() if False else 'no')",
            f"from pathlib import Path; p=Path('{path}'); print(p.read_text() and 'no')",
            f"from pathlib import Path; p=Path('{path}'); t=p.read_text().splitlines(); print('\\n'.join(x for x in t if False))",
            f"from pathlib import Path; p=Path('{path}'); t=p.read_text()\nif True: t='not file'\nprint(t)",
            f"from pathlib import Path; t=open('{path}').read(0); print('noise'); print(t)",
            f"from pathlib import Path; p=Path('{path}'); t=p.read_text().splitlines(); print('\\n'.join(t[i] for i in range(0, 999999999999999999999999999999999999999999)))",
            f"from pathlib import Path; p=Path('{path}'); t=p.read_text(); print('noise'); print(t[:0])",
            f"Path = lambda name: None; print(Path('{path}').read_text())",
            f"def Path(name): return None\nprint(Path('{path}').read_text())",
        )
        for program in programs:
            with self.subTest(program=program):
                events = [{"type": "item.completed", "item": {
                    "type": "command_execution", "exit_code": 0,
                    "command": f'python -c "{program}"', "aggregated_output": "actual file content",
                }}]
                self.assertEqual(runner.skill_activation_evidence(events, "bsp", "prefixes.md"), [])

    def test_correct_answer_alone_is_not_activation(self):
        events = [{
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "БСП и правильный метод"},
        }]
        self.assertEqual(runner.skill_activation_evidence(events, "bsp"), [])


class CdxCommandTests(unittest.TestCase):
    def setUp(self):
        self.case = runner.EvalCase(
            id="test",
            task="Задача",
            reference=None,
            should_trigger=True,
            requires_bsl=False,
            required_patterns=(),
            forbidden_patterns=(),
            activation_patterns=(),
        )

    def test_windows_enables_sandbox_when_user_config_is_ignored(self):
        command = runner.build_cdx_command(
            "cdx", self.case, Path("C:/work"), None, None, platform_name="nt"
        )
        self.assertIn("--ignore-user-config", command)
        self.assertIn('windows.sandbox="unelevated"', command)

    def test_non_windows_does_not_receive_windows_config(self):
        command = runner.build_cdx_command(
            "cdx", self.case, Path("/work"), None, None, platform_name="posix"
        )
        self.assertNotIn('windows.sandbox="unelevated"', command)
        self.assertNotIn("allow_login_shell=false", command)
        self.assertFalse(any(arg.startswith("developer_instructions=") for arg in command))

    def test_windows_uses_utf8_readers_without_user_profiles(self):
        command = runner.build_cdx_command(
            "cdx", self.case, Path("C:/work"), None, None, platform_name="nt"
        )
        self.assertIn("allow_login_shell=false", command)
        self.assertIn('shell_environment_policy.set.PYTHONIOENCODING="utf-8"', command)
        instructions = next(arg for arg in command if arg.startswith("developer_instructions="))
        reading_instructions = json.loads(instructions.split("=", 1)[1])
        self.assertIn("rg -n", reading_instructions)
        self.assertIn("Do not pipe", reading_instructions)
        self.assertIn("Select-String", reading_instructions)
        self.assertEqual(command[-1], self.case.task)

    def test_luna_is_the_default_eval_model(self):
        args = runner.build_parser().parse_args([])
        self.assertEqual(args.model, "gpt-5.6-luna")
        command = runner.build_cdx_command(
            "cdx", self.case, Path("/work"), args.model, None,
            platform_name="posix",
        )
        model_index = command.index("--model")
        self.assertEqual(command[model_index + 1], "gpt-5.6-luna")


class ResponseScoringTests(unittest.TestCase):
    def setUp(self):
        self.case = runner.EvalCase(
            id="test",
            task="test",
            reference="valid.md",
            should_trigger=True,
            requires_bsl=True,
            required_patterns=(r"ТестовыйМодуль\.СтабильныйМетод\s*\(",),
            forbidden_patterns=(r"Опечатка\s*\(",),
            activation_patterns=(),
        )
        self.method_index = runner.load_method_index(SKILL_DIR, FIXTURE_SRC)

    def test_stable_export_passes(self):
        response = "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```"
        score = runner.score_response(self.case, response, self.method_index)
        self.assertTrue(score["passed"])
        self.assertEqual(score["method_accuracy"], 1.0)

    def test_warning_about_another_call_does_not_hide_recommended_code(self):
        suffix = "\n\nТестовыйМодуль.ДругойМетод() использовать не следует."
        good = "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```" + suffix
        score = runner.score_response(self.case, good, self.method_index)
        self.assertEqual(score["known_module_calls"], ["ТестовыйМодуль.СтабильныйМетод"])
        unsafe = "```bsl\nТестовыйМодуль.СтабильныйМетод();\nТестовыйМодуль.Опечатка();\n```" + suffix
        score = runner.score_response(self.case, unsafe, self.method_index)
        self.assertFalse(score["passed"])
        self.assertEqual(score["invalid_methods"], ["ТестовыйМодуль.Опечатка"])

    def test_deictic_warning_about_named_other_method_keeps_public_code(self):
        block = "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```"
        warning = (
            "\n\nСовет не подходит: `ДругойМетод` возвращает плановый срок; "
            "этот метод находится в служебном API, а не в стабильном публичном API."
        )
        self.assertTrue(runner.score_response(self.case, block + warning, self.method_index)["passed"])
        unsafe = block.replace("СтабильныйМетод();", "СтабильныйМетод();\nТестовыйМодуль.Опечатка();")
        self.assertEqual(runner.score_response(self.case, unsafe + warning, self.method_index)["invalid_methods"],
                         ["ТестовыйМодуль.Опечатка"])
        for name in ("СтабильныйМетод", "ТестовыйМодуль.СтабильныйМетод"):
            with self.subTest(name=name):
                self.assertEqual(runner.executable_bsl_blocks(block + warning.replace("ДругойМетод", name)), [])

    def test_deictic_warning_without_named_other_method_still_rejects_code(self):
        block = "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```"
        for warning in (
            "Этот метод не следует вызывать.",
            "Этот метод не подходит для параметра `ДругойМетод`.",
            "Метод `ТестовыйМодуль.СтабильныйМетод` не подходит; этот метод не следует вызывать.",
        ):
            with self.subTest(warning=warning):
                self.assertEqual(runner.executable_bsl_blocks(block + "\n\n" + warning), [])

    def test_positive_clause_does_not_override_warning_about_the_same_call(self):
        warning = "ТестовыйМодуль.СтабильныйМетод использовать не следует."
        recommendation = "Для прикладного кода предназначен ТестовыйМодуль.СтабильныйМетод."
        block = "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```"
        for context in (warning + " " + recommendation, recommendation + " " + warning):
            for response in (context + "\n\n" + block, block + "\n\n" + context):
                with self.subTest(response=response):
                    score = runner.score_response(self.case, response, self.method_index)
                    self.assertFalse(score["passed"])
                    self.assertEqual(runner.executable_bsl_blocks(response), [])

    def test_hook_exemption_does_not_hide_warning_about_a_call_in_its_body(self):
        warning = "ТестовыйМодуль.СтабильныйМетод напрямую вызывать нельзя."
        recommendation = "Для прикладного кода предназначен ТестовыйМодуль.СтабильныйМетод."
        block = (
            "```bsl\nПроцедура ПриОпределенииНастроек(Настройки) Экспорт\n"
            "    ТестовыйМодуль.СтабильныйМетод();\nКонецПроцедуры\n```"
        )
        for context in (warning + " " + recommendation, recommendation + " " + warning):
            for response in (context + "\n\n" + block, block + "\n\n" + context):
                with self.subTest(response=response):
                    self.assertFalse(runner.score_response(self.case, response, self.method_index)["passed"])
                    self.assertEqual(runner.executable_bsl_blocks(response), [])

    def test_warning_without_parentheses_does_not_hide_public_recommendation(self):
        examples = (
            (
                "Прикладной код должен вызывать стабильный API ТестовыйМодуль.СтабильныйМетод; "
                "передавать логин и пароль в хук напрямую не нужно.\n\n",
                "",
            ),
            (
                "Правильный вызов:\n",
                "\n\nВызов ТестовыйМодуль.ДругойМетод использовать не следует. "
                "Для прикладного кода предназначен ТестовыйМодуль.СтабильныйМетод.",
            ),
            (
                "Логин и пароль отдельно передавать не нужно: используйте публичный API "
                "ТестовыйМодуль.СтабильныйМетод.\n\n",
                "",
            ),
            (
                "",
                "\n\nПрямой вызов ТестовыйМодуль.ДругойМетод не подходит. "
                "Используйте экспортный метод общего модуля ТестовыйМодуль из публичного интерфейса.",
            ),
        )
        for prefix, suffix in examples:
            with self.subTest(prefix=prefix, suffix=suffix):
                response = prefix + "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```" + suffix
                score = runner.score_response(self.case, response, self.method_index)
                self.assertTrue(score["passed"])
                self.assertEqual(score["known_module_calls"], ["ТестовыйМодуль.СтабильныйМетод"])
                unsafe = response.replace("СтабильныйМетод();", "СтабильныйМетод();\nТестовыйМодуль.Опечатка();")
                self.assertFalse(runner.score_response(self.case, unsafe, self.method_index)["passed"])

    def test_incidental_negative_notes_do_not_label_recommended_code(self):
        contexts = (
            ("В reference отдельного конструктора параметров нет.\n\n", ""),
            ("", "\n\nМодуль без суффикса Сервер использовать не следует."),
            ("", "\n\nВ клиент-серверном варианте штатная форма не подходит."),
            ("", "\n\nПроверка не гарантирует, что состояние задачи не изменится."),
            ("", "\n\nМетод возвращает строку, отдельно форматировать её не нужно."),
            ("", "\n\nТаблица уже создана БСП; создавать коллекцию в менеджере не нужно."),
            ("", "\n\nПроверка на другом примере дала неверный результат."),
            ("", '\n\nДругие коды, например "НеверныйЛогинИлиПароль", нужно обработать.'),
            ("", '\n\nВозможны, например, `"ОбновлениеНеТребуется"` и `"НеверныйЛогинИлиПароль"`.'),
        )
        for prefix, suffix in contexts:
            with self.subTest(prefix=prefix, suffix=suffix):
                response = prefix + "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```" + suffix
                score = runner.score_response(self.case, response, self.method_index)
                self.assertTrue(score["passed"])
                unsafe = response.replace("СтабильныйМетод();", "СтабильныйМетод();\nТестовыйМодуль.Опечатка();")
                self.assertFalse(runner.score_response(self.case, unsafe, self.method_index)["passed"])

    def test_unqualified_warning_does_not_hide_invalid_call_in_another_fence(self):
        response = (
            "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```\n\n"
            "```bsl\nТестовыйМодуль.Опечатка();\n```\n\n"
            "ДругойМетод() использовать не следует."
        )
        score = runner.score_response(self.case, response, self.method_index)
        self.assertFalse(score["passed"])
        self.assertEqual(score["invalid_methods"], ["ТестовыйМодуль.Опечатка"])

    def test_correction_in_intro_does_not_hide_the_recommended_call(self):
        response = (
            "Совет верен по сути, но имя модуля указано неправильно. "
            "ТестовыйМодуль.СтабильныйМетод — стабильный API для этой задачи.\n\n"
            "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```"
        )
        self.assertEqual(runner.score_response(self.case, response, self.method_index)["known_module_calls"],
                         ["ТестовыйМодуль.СтабильныйМетод"])

    def test_comments_and_strings_do_not_become_api_calls(self):
        response = (
            '```bsl\nТестовыйМодуль.СтабильныйМетод();\n'
            'Сообщить("https://example.test/ТестовыйМодуль.Опечатка()");\n'
            '// ТестовыйМодуль.Опечатка();\n```'
        )
        score = runner.score_response(self.case, response, self.method_index)
        self.assertTrue(score["passed"])
        self.assertEqual(score["known_module_calls"], ["ТестовыйМодуль.СтабильныйМетод"])
        self.assertEqual(score["invalid_methods"], [])

    def test_missing_export_is_a_definite_hallucination(self):
        response = "```bsl\nТестовыйМодуль.СтабильныйМетод();\nТестовыйМодуль.Опечатка();\n```"
        score = runner.score_response(self.case, response, self.method_index)
        self.assertFalse(score["passed"])
        self.assertEqual(score["invalid_methods"], ["ТестовыйМодуль.Опечатка"])

    def test_forbidden_call_in_prose_is_allowed_but_code_is_not(self):
        prose = (
            "Не вызывайте Опечатка().\n"
            "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```"
        )
        code = (
            "```bsl\nТестовыйМодуль.СтабильныйМетод();\nОпечатка();\n```"
        )
        self.assertTrue(runner.score_response(self.case, prose, self.method_index)["passed"])
        self.assertFalse(runner.score_response(self.case, code, self.method_index)["passed"])

    def test_explicit_negative_code_block_is_not_a_recommended_call(self):
        response = (
            "Правильный вариант:\n"
            "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```\n"
            "Так вызывать нельзя:\n"
            "```bsl\nТестовыйМодуль.Опечатка();\n```"
        )
        score = runner.score_response(self.case, response, self.method_index)
        self.assertTrue(score["passed"])
        self.assertEqual(score["invalid_methods"], [])

    def test_real_negative_phrasings_are_not_executable_recommendations(self):
        examples = (
            (
                "Ложный очевидный API:",
                "",
            ),
            (
                "Не существует публичного вызова вида:",
                "",
            ),
            (
                "Серверного публичного метода нет. В частности:",
                "— этот метод не запускает операцию.",
            ),
            (
                "Прямого вызова вида:",
                "в прикладном коде быть не должно.",
            ),
        )
        for prefix, suffix in examples:
            with self.subTest(prefix=prefix, suffix=suffix):
                response = (
                    "Правильный вариант:\n"
                    "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```\n\n"
                    f"{prefix}\n"
                    "```bsl\nТестовыйМодуль.СлужебныйМетод();\n```\n"
                    f"{suffix}"
                )
                score = runner.score_response(self.case, response, self.method_index)
                self.assertTrue(score["passed"])
                self.assertEqual(score["unsafe_calls"], [])

    def test_negative_context_propagates_across_or_alternatives(self):
        response = (
            "Правильный вариант:\n"
            "```bsl\nТестовыйМодуль.СтабильныйМетод();\n```\n\n"
            "Очевидный вызов вида:\n"
            "```bsl\nТестовыйМодуль.СлужебныйМетод();\n```\n\n"
            "или\n\n"
            "```bsl\nТестовыйМодуль.СлужебныйМетод();\n```\n\n"
            "Таких публичных методов нет."
        )
        score = runner.score_response(self.case, response, self.method_index)
        self.assertTrue(score["passed"])
        self.assertEqual(score["unsafe_calls"], [])
        self.assertEqual(
            runner.executable_bsl_blocks(response),
            ["ТестовыйМодуль.СтабильныйМетод();\n"],
        )

    def test_member_call_split_across_lines_is_detected(self):
        response = "```bsl\nТестовыйМодуль\n    .СтабильныйМетод();\n```"
        score = runner.score_response(self.case, response, self.method_index)
        self.assertTrue(score["passed"])
        self.assertEqual(score["known_module_calls"], ["ТестовыйМодуль.СтабильныйМетод"])

    def test_service_export_is_unsafe(self):
        case = runner.EvalCase(
            id="service",
            task="test",
            reference=None,
            should_trigger=True,
            requires_bsl=True,
            required_patterns=(r"ТестовыйМодуль\.СлужебныйМетод\s*\(",),
            forbidden_patterns=(),
            activation_patterns=(),
        )
        response = "```bsl\nТестовыйМодуль.СлужебныйМетод();\n```"
        score = runner.score_response(case, response, self.method_index)
        self.assertFalse(score["passed"])
        self.assertEqual(score["unsafe_calls"][0]["call"], "ТестовыйМодуль.СлужебныйМетод")

    def test_hook_implementation_survives_warning_against_direct_hook_calls(self):
        case = next(
            item for item in runner.load_cases(runner.DEFAULT_CASES)
            if item.id == "prefix-hook-not-call"
        )
        response = (
            "Реализуйте хук в модуле ПрефиксацияОбъектовПереопределяемый. "
            "БСП вызывает его сама; напрямую вызывать модуль из прикладного кода не нужно.\n"
            "```bsl\n"
            "Процедура ПолучитьПрефиксообразующиеРеквизиты(Объекты) Экспорт\n"
            "    СтрокаОбъекта = Объекты.Добавить();\n"
            "    СтрокаОбъекта.Реквизит = \"ГоловнаяОрганизация\";\n"
            "КонецПроцедуры\n```")
        blocks = runner.executable_bsl_blocks(response)
        self.assertEqual(len(blocks), 1)
        self.assertTrue(
            runner.score_response(case, response, {})["passed"]
        )

    def test_hook_implementation_survives_warning_inside_code_comment(self):
        response = """```bsl
// Прикладная реализация хука БСП.
// БСП вызывает эту процедуру; напрямую её не вызывают.
Процедура ПолучитьПрефиксообразующиеРеквизиты(Объекты) Экспорт
    СтрокаОбъектов = Объекты.Добавить();
КонецПроцедуры
```"""
        self.assertEqual(len(runner.executable_bsl_blocks(response)), 1)
        negative = response.replace("// Прикладная реализация хука БСП.", "// Антипаттерн: неверная реализация.")
        self.assertEqual(runner.executable_bsl_blocks(negative), [])

    def test_hook_implementation_survives_warning_after_code_block(self):
        response = (
            "```bsl\n"
            "Процедура ПриОпределенииНастроекПечати(Настройки) Экспорт\n"
            "    Настройки.ПриДобавленииКомандПечати = Истина;\n"
            "КонецПроцедуры\n```\n"
            "БСП вызывает hook сама; напрямую вызывать его не нужно."
        )
        self.assertEqual(len(runner.executable_bsl_blocks(response)), 1)

    def test_print_registration_requires_code_for_both_registration_steps(self):
        case = next(
            item for item in runner.load_cases(runner.DEFAULT_CASES)
            if item.id == "print-object-registration"
        )
        correct = (
            "```bsl\n"
            "Процедура ПриОпределенииНастроекПечати(Настройки) Экспорт\n"
            "    Настройки.ОбъектыПечати.Добавить(Документы.МойДокумент);\n"
            "КонецПроцедуры\n```\n"
            "```bsl\n"
            "Процедура ПриОпределенииНастроекПечати(Настройки) Экспорт\n"
            "    Настройки.ПриДобавленииКомандПечати = Истина;\n"
            "КонецПроцедуры\n```")
        incomplete = (
            "ОбъектыПечати зарегистрированы.\n"
            "```bsl\n"
            "Процедура ПриОпределенииНастроекПечати(Настройки) Экспорт\n"
            "    Настройки.ОбъектыПечати.Добавить(Документы.МойДокумент);\n"
            "КонецПроцедуры\n```")
        same_block = (
            "```bsl\n"
            "Процедура ПриОпределенииНастроекПечати(Настройки) Экспорт\n"
            "    Настройки.ОбъектыПечати.Добавить(Документы.МойДокумент);\n"
            "КонецПроцедуры\n"
            "Процедура ПриОпределенииНастроекПечати(Настройки) Экспорт\n"
            "    Настройки.ПриДобавленииКомандПечати = Истина;\n"
            "КонецПроцедуры\n```")
        self.assertTrue(runner.score_response(case, correct, {})["passed"])
        self.assertFalse(runner.score_response(case, incomplete, {})["passed"])
        self.assertFalse(runner.score_response(case, same_block, {})["passed"])

    def test_required_code_pattern_checks_call_argument_order_and_directive_context(self):
        case = runner.EvalCase(
            id="ordered-context", task="test", reference=None, should_trigger=True,
            requires_bsl=True, required_patterns=(r"Готово",), forbidden_patterns=(),
            activation_patterns=(),
            required_code_patterns=(
                r"(?s)&НаСервере\s*\nПроцедура\s+Проверить\s*\(\s*Контрагент\s*,\s*Отказ\s*\)",
            ),
        )
        proper = (
            "Готово\n```bsl\n&НаСервере\n"
            "Процедура Проверить(Контрагент, Отказ)\nКонецПроцедуры\n```")
        wrong_order = proper.replace("Контрагент, Отказ", "Отказ, Контрагент")
        wrong_context = proper.replace("&НаСервере", "&НаКлиенте")
        self.assertTrue(runner.score_response(case, proper, {})["passed"])
        self.assertFalse(runner.score_response(case, wrong_order, {})["passed"])
        self.assertFalse(runner.score_response(case, wrong_context, {})["passed"])

    def test_scoped_green_requires_expected_reference_read(self):
        case = runner.EvalCase(
            id="scoped", task="test", reference="prefixes.md", should_trigger=True,
            requires_bsl=False, required_patterns=(r"Ответ",), forbidden_patterns=(),
            activation_patterns=(),
        )
        response = "Ответ по reference"
        unopened_reference = runner.score_response(
            case, response, {}, skill_activated=True, require_activation=True,
            require_reference=True, reference_read=False,
        )
        opened_reference = runner.score_response(
            case, response, {}, skill_activated=True, require_activation=True,
            require_reference=True, reference_read=True,
        )
        self.assertFalse(unopened_reference["passed"])
        self.assertFalse(unopened_reference["reference_ok"])
        self.assertTrue(opened_reference["passed"])
        self.assertTrue(opened_reference["reference_ok"])

    def test_unscoped_and_negative_cases_do_not_require_reference_read(self):
        case = runner.EvalCase(
            id="unscoped", task="test", reference=None, should_trigger=True,
            requires_bsl=False, required_patterns=(r"Ответ",), forbidden_patterns=(),
            activation_patterns=(),
        )
        score = runner.score_response(
            case, "Ответ", {}, skill_activated=True, require_activation=True,
        )
        self.assertTrue(score["passed"])
        self.assertTrue(score["reference_ok"])

    def test_required_code_pattern_does_not_match_prose_or_negative_fence(self):
        case = runner.EvalCase(
            id="code-only", task="test", reference=None, should_trigger=True,
            requires_bsl=False, required_patterns=(r"Ответ",), forbidden_patterns=(),
            activation_patterns=(), required_code_patterns=(r"ТестовыйМодуль\.Вызов\s*\(\)",),
        )
        prose = "Ответ: ТестовыйМодуль.Вызов()"
        negative = "Ответ\nТак делать нельзя:\n```bsl\nТестовыйМодуль.Вызов();\n```"
        self.assertFalse(runner.score_response(case, prose, {})["passed"])
        self.assertFalse(runner.score_response(case, negative, {})["passed"])

    def test_forbidden_direct_hook_call_allows_hook_implementation(self):
        case = runner.EvalCase(
            id="hook-boundary", task="test", reference=None, should_trigger=True,
            requires_bsl=True, required_patterns=(r"Готово",), forbidden_patterns=(),
            activation_patterns=(),
            forbidden_code_patterns=(
                r"ПрефиксацияОбъектовПереопределяемый\.ПолучитьПрефиксообразующиеРеквизиты\s*\(",
            ),
        )
        direct_call = "Готово\n```bsl\nПрефиксацияОбъектовПереопределяемый.ПолучитьПрефиксообразующиеРеквизиты();\n```"
        implementation = (
            "Готово\n```bsl\nПроцедура ПолучитьПрефиксообразующиеРеквизиты(Реквизиты)\n"
            "КонецПроцедуры\n```")
        self.assertFalse(runner.score_response(case, direct_call, {})["passed"])
        self.assertTrue(runner.score_response(case, implementation, {})["passed"])

    def test_negative_case_must_not_show_activation_markers(self):
        case = runner.EvalCase(
            id="negative",
            task="test",
            reference=None,
            should_trigger=False,
            requires_bsl=False,
            required_patterns=(r"Ответ",),
            forbidden_patterns=(),
            activation_patterns=(r"БСП",),
        )
        clean = runner.score_response(
            case, "Ответ", {}, skill_activated=False, require_activation=True
        )
        contaminated = runner.score_response(
            case, "Ответ по БСП", {}, skill_activated=True, require_activation=True
        )
        self.assertTrue(clean["passed"])
        self.assertFalse(contaminated["passed"])


class CorpusCriteriaTests(unittest.TestCase):
    @staticmethod
    def case(case_id):
        return next(case for case in runner.load_cases(runner.DEFAULT_CASES) if case.id == case_id)

    def test_safe_write_accepts_equivalent_module_correction(self):
        case = self.case("update-safe-write-module-name")
        response = (
            "В совете указан не тот общий модуль: ОбновлениеИнформационнойБазыСервер.\n\n"
            "Правильный минимальный вызов:\n```bsl\n"
            "ОбновлениеИнформационнойБазы.ЗаписатьДанные(ДокументОбъект);\n```"
        )
        self.assertTrue(runner.score_response(case, response, {})["passed"])
        alternative = (
            "Общий модуль называется ОбновлениеИнформационнойБазы, без суффикса `Сервер`.\n\n"
            "Правильный минимальный вызов:\n```bsl\n"
            "ОбновлениеИнформационнойБазы.ЗаписатьОбъект(ДокументОбъект, Ложь, Ложь);\n```"
        )
        self.assertTrue(runner.score_response(case, alternative, {})["passed"])

    def test_safe_write_requires_executable_call_with_safe_flags(self):
        case = self.case("update-safe-write-module-name")
        prefix = "ОбновлениеИнформационнойБазыСервер не существует.\n\nПравильный вызов:\n"
        for method in ("ЗаписатьДанные", "ЗаписатьОбъект"):
            for arguments in ("ДокументОбъект", "ДокументОбъект, Ложь, Ложь",
                              "ДокументОбъект, Неопределено, Ложь", "ДокументОбъект, , Ложь"):
                response = prefix + f"```bsl\nОбновлениеИнформационнойБазы.{method}({arguments});\n```"
                self.assertTrue(runner.score_response(case, response, {})["passed"])
            for arguments in ("ДокументОбъект, Истина, Ложь", "ДокументОбъект, Ложь, Истина"):
                response = prefix + f"```bsl\nОбновлениеИнформационнойБазы.{method}({arguments});\n```"
                self.assertFalse(runner.score_response(case, response, {})["passed"])
        for method, mode, expected in (
            ("ЗаписатьОбъект", "РежимЗаписиДокумента.Запись", True),
            ("ЗаписатьОбъект", "РежимЗаписиДокумента.Проведение", False),
            ("ЗаписатьДанные", "РежимЗаписиДокумента.Запись", False),
        ):
            response = prefix + f"```bsl\nОбновлениеИнформационнойБазы.{method}(ДокументОбъект, Ложь, Ложь, {mode});\n```"
            self.assertEqual(runner.score_response(case, response, {})["passed"], expected)
        response = prefix + (
            "ОбновлениеИнформационнойБазы.ЗаписатьДанные(ДокументОбъект).\n\n"
            "```bsl\n// Здесь должен быть правильный вызов.\n```"
        )
        self.assertFalse(runner.score_response(case, response, {})["passed"])

    def test_safe_write_comment_or_string_is_not_executable_evidence(self):
        case = self.case("update-safe-write-module-name")
        prefix = "ОбновлениеИнформационнойБазыСервер не существует.\n\nПравильный вызов:\n"
        for code in (
            "// ОбновлениеИнформационнойБазы.ЗаписатьДанные(ДокументОбъект);",
            'Сообщить("ОбновлениеИнформационнойБазы.ЗаписатьДанные(ДокументОбъект)");',
        ):
            score = runner.score_response(case, prefix + f"```bsl\n{code}\n```", {})
            self.assertFalse(score["passed"])
        response = prefix + '''```bsl
ОбновлениеИнформационнойБазы.ЗаписатьДанные(
    ДокументОбъект,
    Ложь, // Отключить регистрацию
    Ложь  // Отключить бизнес-логику
);
```'''
        self.assertTrue(runner.score_response(case, response, {})["passed"])

    def test_equivalent_native_warning_phrasings_are_accepted(self):
        case = self.case("update-safe-write-module-name")
        response = (
            "В имени модуля лишний суффикс `Сервер`.\n\n"
            "Правильный вызов:\n```bsl\n"
            "ОбновлениеИнформационнойБазы.ЗаписатьДанные(ДокументОбъект);\n```"
        )
        self.assertTrue(runner.score_response(case, response, {})["passed"])
        explains_flags = response.replace(
            "ЗаписатьДанные(ДокументОбъект)", "ЗаписатьДанные(ДокументОбъект, Ложь, Ложь)"
        ) + "\n\nПервое Ложь запрещает регистрацию на узлах обмена, второе отключает бизнес-логику."
        self.assertTrue(runner.score_response(case, explains_flags, {})["passed"])
        fundamental = self.case("fundamentals-module-and-api-boundaries")
        response = '''ОбщегоНазначения — сервер; ОбщегоНазначенияКлиент — клиент.
ОбщегоНазначенияКлиентСервер — общие алгоритмы без обращения к БД.
ОбщегоНазначенияВызовСервера — серверный модуль с разрешённым вызовом с клиента.
ОбщегоНазначенияСлужебный не существует; есть ОбщегоНазначенияСлужебныйКлиентСервер.
ПрограммныйИнтерфейс — публичный; УстаревшиеПроцедурыИФункции — устаревший.
СлужебныйПрограммныйИнтерфейс — служебный; совместимость его методов **не гарантируется**.'''
        self.assertTrue(runner.score_response(fundamental, response, {})["passed"])
        separate_sentence = response.replace(
            "совместимость его методов **не гарантируется**",
            "обратная совместимость гарантируется для стабильного API. Для служебных методов она **не гарантируется**",
        )
        self.assertTrue(runner.score_response(fundamental, separate_sentence, {})["passed"])
        wrong_guarantee = response.replace("**не гарантируется**", "гарантируется")
        self.assertFalse(runner.score_response(fundamental, wrong_guarantee, {})["passed"])
        for server_phrase in (
            "ОбщегоНазначенияВызовСервера — серверные методы для вызова с клиента.",
            "Для вызовов с клиента предназначен серверный модуль `ОбщегоНазначенияВызовСервера`.",
        ):
            variant = response.replace(
                "ОбщегоНазначенияВызовСервера — серверный модуль с разрешённым вызовом с клиента.", server_phrase
            )
            self.assertTrue(runner.score_response(fundamental, variant, {})["passed"])

    def test_hook_warning_accepts_reverse_word_order_without_allowing_direct_call(self):
        case = self.case("connected-command-hook-boundary")
        frame = '''ПодключаемыеКомандыПереопределяемый:\n```bsl
Процедура ПриОпределенииКомандПодключенныхКОбъекту(
        НастройкиФормы, Источники, ПодключенныеОтчетыИОбработки, Команды) Экспорт
    Если Источники.Строки.Найти("Документ.ЗаказКлиента", "ПолноеИмя") = Неопределено Тогда
        Возврат;
    КонецЕсли;
    Команда = Команды.Добавить();
    Команда.Вид = "СверкаОплаты";
    Команда.Обработчик = "СверкаОплатыКлиент.ВыполнитьСверку";
    ПодключаемыеКоманды.ДобавитьУсловиеВидимостиКоманды(Команда, "Проведен", Истина);
КонецПроцедуры
```'''
        for warning in (
            "Сам хук напрямую вызывать нельзя.", "Хук вызывает сама БСП.",
            "Хук реализуется приложением, а вызывает его БСП. Напрямую вызывать хук нельзя.",
            "Напрямую вызывать ПодключаемыеКомандыПереопределяемый."
            "ПриОпределенииКомандПодключенныхКОбъекту нельзя.",
        ):
            self.assertTrue(runner.score_response(case, frame + "\n\n" + warning, {})["passed"])
        self.assertFalse(runner.score_response(case, frame, {})["passed"])
        for broken in (
            frame.replace(") Экспорт", ")"),
            frame.replace('Команда.Вид = "СверкаОплаты";', '// Вид не указан.'),
            frame.replace('Команда.Вид = "СверкаОплаты";', 'Команда.ТипПараметраКоманды = "СверкаОплаты";'),
        ):
            self.assertFalse(runner.score_response(case, broken + "\n\nХук нельзя вызывать напрямую.", {})["passed"])
        unsafe = frame.replace("КонецПроцедуры", "ПодключаемыеКомандыПереопределяемый."
                               "ПриОпределенииКомандПодключенныхКОбъекту();\nКонецПроцедуры")
        self.assertFalse(runner.score_response(case, unsafe + "\n\nХук нельзя вызывать напрямую.", {})["passed"])
        wrong_visibility = frame.replace('"Проведен", Истина',
                                         '"Проведен", Истина, ВидСравненияКомпоновкиДанных.НеРавно')
        self.assertFalse(runner.score_response(case, wrong_visibility + "\n\nХук нельзя вызывать напрямую.", {})["passed"])

    def test_classifier_error_handling_rule_is_bounded_and_provenance_aware(self):
        case = self.case("classifiers-update-public-boundary")

        def score(body):
            response = (
                "РаботаСКлассификаторамиВызовСервера — служебный API.\n```bsl\n"
                "Результат = РаботаСКлассификаторами.ОбновитьКлассификаторы(Идентификаторы);\n"
                f"{body}\n```"
            )
            return runner.score_response(case, response, {})["passed"]

        self.assertFalse(
            score('ВызватьИсключение "Не удалось обновить" + Результат.КодОшибки;'),
            "an unconditional raise executes for normal statuses",
        )

        good = (
            'Если Не ПустаяСтрока(Результат.КодОшибки) И '
            'Результат.КодОшибки <> "ОбновлениеНеТребуется" Тогда\n'
            '    ВызватьИсключение "Не удалось обновить: " + Результат.КодОшибки;\n'
            'КонецЕсли;'
        )
        self.assertTrue(score(good))
        self.assertTrue(score(
            'Если Не ПустаяСтрока(Результат.КодОшибки)\n'
            '        И Результат.КодОшибки <> "ОбновлениеНеТребуется" Тогда\n'
            '    ВызватьИсключение\n        "Ошибка: " + Результат.КодОшибки;\nКонецЕсли;'
        ))
        self.assertTrue(score(
            'Если ЗначениеЗаполнено(Результат.КодОшибки) И '
            'Результат.КодОшибки <> "ОбновлениеНеТребуется" Тогда\n'
            '    ОбщегоНазначения.СообщитьПользователю(\n'
            '        "Ошибка обновления");\nКонецЕсли;'
        ))
        self.assertTrue(score('Сообщить("Код: "+Результат.КодОшибки);'))
        self.assertTrue(score('ЗаписьЖурналаРегистрации("Обновление", , , , Результат.КодОшибки);'))
        self.assertFalse(score('Если НеизвестноеУсловие Тогда\nСообщить(Результат.КодОшибки);\nКонецЕсли;'))
        self.assertFalse(score('Код = Результат.КодОшибки; Код = "Код"; Сообщить(Код);'))
        self.assertFalse(score('Результат.КодОшибки = ""; Сообщить(Результат.КодОшибки);'))
        self.assertFalse(score('Результат = Неопределено; Сообщить(Результат.КодОшибки);'))
        self.assertFalse(score('FakeModule.Сообщить(Результат.КодОшибки);'))
        self.assertFalse(score('Если Результат.КодОшибки = "" Тогда\nВызватьИсключение "ошибка";\nКонецЕсли;'))
        self.assertFalse(score('Сообщить("готово");'))
        self.assertFalse(score('ВызватьИсключение "ошибка";'))
        self.assertTrue(score(
            'Если ЗначениеЗаполнено(Результат.КодОшибки) И '
            'Результат.КодОшибки <> "ОбновлениеНеТребуется" Тогда\n'
            '    Сообщить(Результат.КодОшибки);\nКонецЕсли;'
        ))
        self.assertTrue(score(
            'Если Результат.КодОшибки = "" ИЛИ '
            'Результат.КодОшибки = "ОбновлениеНеТребуется" Тогда\n'
            '    Сообщить("Все в порядке");\nИначе\n'
            '    ВызватьИсключение Результат.КодОшибки;\nКонецЕсли;'
        ))
        self.assertTrue(score(
            'code = Результат.КодОшибки; code2 = code;\n'
            'Если Не ПустаяСтрока(code2) И code2 <> "ОбновлениеНеТребуется" Тогда\n'
            '    Сообщить("Ошибка: " + code2);\nКонецЕсли;'
        ))
        self.assertFalse(score(
            'code = Результат.КодОшибки; code2 = code; code2 = "";\n'
            'Сообщить("Ошибка: " + code2);'
        ))
        self.assertFalse(score(
            'Если Результат.КодОшибки = "ОбновлениеНеТребуется" Тогда\n'
            '    ВызватьИсключение Результат.КодОшибки;\nКонецЕсли;'
        ))
        self.assertTrue(score(
            'code = Результат.КодОшибки; code2 = code;\n'
            'Если Не ПустаяСтрока(code2) И code2 <> "ОбновлениеНеТребуется" Тогда\n'
            '    ВызватьИсключение "Ошибка: " + code2;\nКонецЕсли;'
        ))
        self.assertTrue(score(
            'Если Не ПустаяСтрока(Результат.КодОшибки) Тогда\n'
            '    ОбщегоНазначения.СообщитьПользователю("Ошибка: " + Результат.КодОшибки);\nКонецЕсли;'
        ))
        self.assertTrue(score(
            'Если Не ПустаяСтрока(Результат.КодОшибки) Тогда\n'
            '    ЗаписьЖурналаРегистрации("Обновление", , , , Результат.КодОшибки);\nКонецЕсли;'
        ))
        self.assertFalse(score('// Сообщить(Результат.КодОшибки);'))
        self.assertFalse(score('Текст = "Сообщить(Результат.КодОшибки);";'))
        self.assertFalse(score('ВызватьИсключение "Не удалось");'))
        self.assertFalse(score(
            'Если Не ПустаяСтрока(Результат.КодОшибки) Тогда\n'
            '    Для каждого Элемент Из Массив Цикл\nКонецЦикла;\n'
            '    Сообщить(Результат.КодОшибки);\nКонецЕсли;'
        ))
        rule = case.error_handling_rule
        source = 'Результат = РаботаСКлассификаторами.ОбновитьКлассификаторы(Идентификаторы);'
        self.assertFalse(runner.error_handling_rule_satisfied([
            'Сообщить(Результат.КодОшибки);', source
        ], rule))
        self.assertFalse(runner.error_handling_rule_satisfied([
            source, 'Если Не ПустаяСтрока(Результат.КодОшибки) Тогда\\n'
            'Сообщить(Результат.КодОшибки);\\nКонецЕсли;'
        ], rule))
        self.assertFalse(runner.error_handling_rule_satisfied([source + '\\n' * 65537], rule))

    def test_classifier_boundary_accepts_natural_warning_word_order(self):
        case = self.case("classifiers-update-public-boundary")
        code = ('\n```bsl\nРезультат = РаботаСКлассификаторами.'
                'ОбновитьКлассификаторы(Идентификаторы);\n'
                'Сообщить(Результат.КодОшибки);\n```')
        for warning in (
            "РаботаСКлассификаторамиВызовСервера: вызывать его вместо документированного метода не следует.",
            "РаботаСКлассификаторамиВызовСервера.ОбновитьКлассификаторы не существует в БСП 3.1.11.",
        ):
            with self.subTest(warning=warning):
                self.assertTrue(runner.score_response(case, warning + code, {})["passed"])

    def test_error_policy_keeps_fences_branches_and_effect_locations_independent(self):
        rule = self.case("classifiers-update-public-boundary").error_handling_rule
        source = "Результат = РаботаСКлассификаторами.ОбновитьКлассификаторы(Идентификаторы);\n"
        self.assertFalse(runner.error_handling_rule_satisfied(
            [source, source + 'ВызватьИсключение "ошибка";'], rule))
        self.assertFalse(runner.error_handling_rule_satisfied([source + '''
Если Не ПустаяСтрока(Результат.КодОшибки) Тогда
    // обработать ошибку
КонецЕсли;
Сообщить("Успешно");
'''], rule))
        self.assertTrue(runner.error_handling_rule_satisfied([source + '''
Если Результат.КодОшибки = "" Тогда
    Сообщить("Успех");
ИначеЕсли Результат.КодОшибки = "ОбновлениеНеТребуется" Тогда
    Сообщить("Данные актуальны");
Иначе
    Если ЗначениеЗаполнено(Результат.КодОшибки) Тогда
        Сообщить("Ошибка");
    Иначе
        Сообщить("Неприменимая ветка");
    КонецЕсли;
КонецЕсли;
'''], rule))
        self.assertFalse(runner.error_handling_rule_satisfied([source + '''
Если Результат.КодОшибки = "" Тогда
    ВызватьИсключение "Нормальный статус";
Иначе
    Сообщить(Результат.КодОшибки);
КонецЕсли;
'''], rule))
        self.assertFalse(runner.error_handling_rule_satisfied([source +
            "Если " + " и ".join(["ЗначениеЗаполнено(Результат.КодОшибки)"] * 256) +
            " Тогда\nСообщить(Результат.КодОшибки);\nКонецЕсли;"], rule))
        self.assertFalse(runner.error_handling_rule_satisfied([source +
            ("Если Не ПустаяСтрока(Результат.КодОшибки) Тогда\n" * 40) +
            "Сообщить(Результат.КодОшибки);\n" + ("КонецЕсли;\n" * 40)], rule))

    def test_fundamentals_requires_server_context_for_server_call_module(self):
        case = self.case("fundamentals-module-and-api-boundaries")
        response = '''ОбщегоНазначения — сервер; ОбщегоНазначенияКлиент — клиент.
ОбщегоНазначенияКлиентСервер — общие алгоритмы без обращения к БД.
ОбщегоНазначенияВызовСервера — серверный общий модуль с разрешённым вызовом с клиента.
ОбщегоНазначенияСлужебный не существует; есть ОбщегоНазначенияСлужебныйКлиентСервер.
ПрограммныйИнтерфейс — публичный; СлужебныйПрограммныйИнтерфейс — служебный;
УстаревшиеПроцедурыИФункции — устаревший.
Для служебных методов обратная совместимость не гарантируется.'''
        self.assertTrue(runner.score_response(case, response, {})["passed"])
        natural_correction = response.replace(
            "ОбщегоНазначенияСлужебный не существует",
            "Имя ОбщегоНазначенияСлужебный для этого семейства неверно",
        )
        self.assertTrue(runner.score_response(case, natural_correction, {})["passed"])
        wrong_module = response.replace("ОбщегоНазначенияСлужебный не существует",
                                        "ОбщегоНазначенияСлужебный — реальный серверный модуль")
        self.assertFalse(runner.score_response(case, wrong_module, {})["passed"])
        wrong_context = response.replace("серверный общий модуль с разрешённым вызовом с клиента",
                                         "клиентский модуль, который делает серверный вызов")
        self.assertFalse(runner.score_response(case, wrong_context, {})["passed"])


class StagingTests(unittest.TestCase):
    def test_fingerprint_uses_posix_name_order_on_every_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            files = {"SKILL.md": b"router", "agents/openai.yaml": b"metadata",
                     "references/topic.md": b"reference", "scripts/api.py": b"script"}
            digest = hashlib.sha256()
            for name, data in sorted(files.items()):
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                digest.update(name.encode("utf-8") + b"\0" + data + b"\0")
            self.assertEqual(runner.skill_sha256(source), digest.hexdigest())

    def test_staging_copies_and_cleans_only_target_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / ".agents" / "skills" / "bsp"
            other = root / ".agents" / "skills" / "other" / "SKILL.md"
            other.parent.mkdir(parents=True)
            other.write_text("other", encoding="utf-8")
            with runner.staged_skill(SKILL_DIR, target):
                self.assertTrue((target / "SKILL.md").is_file())
                self.assertTrue(other.is_file())
            self.assertFalse(target.exists())
            self.assertTrue(other.is_file())

    def test_python_cache_is_not_part_of_shipped_staging_or_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "SKILL.md").write_text("# Skill", encoding="utf-8")
            reference = source / "references" / "topic.md"
            reference.parent.mkdir()
            reference.write_text("Verified scenario", encoding="utf-8")
            before = runner.skill_sha256(source)
            cache = source / "scripts" / "__pycache__" / "api.cpython-312.pyc"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b"machine-specific bytecode")
            (source / "legacy.pyc").write_bytes(b"old bytecode")
            self.assertEqual(runner.skill_sha256(source), before)
            target = root / "consumer" / ".agents" / "skills" / "bsp"
            with runner.staged_skill(source, target):
                self.assertEqual(runner.skill_sha256(target), before)
                self.assertFalse(list(target.rglob("*.pyc")))
                self.assertFalse(list(target.rglob("__pycache__")))
            reference.write_text("Changed scenario", encoding="utf-8")
            self.assertNotEqual(runner.skill_sha256(source), before)

    def test_staging_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ".agents" / "skills" / "bsp"
            target.mkdir(parents=True)
            with self.assertRaisesRegex(runner.EvalError, "overwrite"):
                with runner.staged_skill(SKILL_DIR, target):
                    pass


class ExecutionStatusTests(unittest.TestCase):
    @staticmethod
    def _execution(**overrides):
        execution = {
            "returncode": 0,
            "timed_out": False,
            "tool_policy_blocked": False,
            "response": "Готово",
            "stderr_tail": "",
            "score": {"passed": True},
        }
        execution.update(overrides)
        return execution

    def test_execution_status_distinguishes_quality_infrastructure_and_incomplete(self):
        self.assertEqual(runner.execution_status(self._execution()), "completed")
        self.assertEqual(
            runner.execution_status(self._execution(score={"passed": False})),
            "quality_failed",
        )
        self.assertEqual(
            runner.execution_status(self._execution(timed_out=True)),
            "infrastructure_failed",
        )
        self.assertEqual(
            runner.execution_status(self._execution(response="")),
            "incomplete",
        )

    def test_corrupt_tool_output_is_infrastructure_even_when_answer_passes(self):
        event = {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "Get-Content -Encoding UTF8 reference.md",
                "exit_code": 0,
                "aggregated_output": "# \ufffd\ufffd\ufffd",
            },
        }
        stdout = json.dumps(event) + '\n' + json.dumps({
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "Готово"},
        })
        completed = runner.subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            runner.subprocess, "run", return_value=completed
        ):
            execution = runner.run_cdx(
                "cdx", ParallelExecutionTests._case("decode-error"), Path(tmp),
                Path(tmp), "green", 1, None, None, 10, "bsp",
            )
        execution["score"] = {"passed": True}
        self.assertEqual(execution["tool_output_decode_errors"], [{
            "command": "Get-Content -Encoding UTF8 reference.md",
            "replacement_characters": 3,
        }])
        self.assertEqual(runner.infrastructure_reason(execution), "tool_output_encoding")
        self.assertEqual(runner.execution_status(execution), "infrastructure_failed")
        self.assertIsNone(
            runner.resume_run_matrix([ParallelExecutionTests._case("decode-error")], 1,
                                     {"decode-error": [execution]})[0][0]
        )

    def test_utf8_tool_output_is_not_an_encoding_failure(self):
        events = [{
            "type": "item.completed",
            "item": {
                "type": "command_execution", "exit_code": 0,
                "command": "rg -n '^' reference.md",
                "aggregated_output": "1:# Печать и варианты отчётов",
            },
        }]
        self.assertEqual(runner.tool_output_decode_errors(events), [])

    def test_encoding_check_allows_only_known_utf8_truncation_boundaries(self):
        outputs = [
            "cf/Тип\ufffd\n... 162166 bytes omitted ...\nPicture.xml",
            "Module.bsl\n... 12345 bytes omitted ...\n\ufffdавила.xml",
        ]
        for output in outputs:
            with self.subTest(output=output):
                events = [{"type": "item.completed", "item": {
                    "type": "command_execution", "exit_code": 0,
                    "command": "rg --files", "aggregated_output": output,
                }}]
                self.assertEqual(runner.tool_output_decode_errors(events), [])
        events[0]["item"]["aggregated_output"] = "\ufffd\n... 10 bytes omitted ...\n\ufffd"
        self.assertEqual(runner.tool_output_decode_errors(events)[0]["replacement_characters"], 2)
        for output in ("cf/Тип\ufffd", "\ufffd\ufffd\n... 10 bytes omitted ...\nvalid",
                       "bad\ufffd text\n... 10 bytes omitted ...\n\ufffdtail"):
            with self.subTest(output=output):
                events[0]["item"]["aggregated_output"] = output
                self.assertEqual(runner.tool_output_decode_errors(events)[0]["replacement_characters"], 1)

    def test_encoding_check_ignores_failed_commands_and_agent_prose(self):
        events = [{
            "type": "item.completed",
            "item": {
                "type": "command_execution", "exit_code": 1,
                "command": "failed-reader", "aggregated_output": "\ufffd",
            },
        }, {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "\ufffd"},
        }]
        self.assertEqual(runner.tool_output_decode_errors(events), [])

    def test_infrastructure_reason_is_classified(self):
        examples = {
            "quota exceeded": "quota_or_rate_limit",
            "authentication required": "authentication",
            "connection reset by peer": "network",
            "model is unavailable": "model_unavailable",
        }
        for stderr, expected in examples.items():
            with self.subTest(stderr=stderr):
                execution = self._execution(returncode=1, stderr_tail=stderr)
                self.assertEqual(runner.infrastructure_reason(execution), expected)


class SummaryTests(unittest.TestCase):
    def test_green_gate_requires_all_scoped_references_to_be_read(self):
        summary = {
            "pass_rate": 1.0,
            "activation_rate": 1.0,
            "reference_cases": 2,
            "reference_read_rate": 0.5,
            "invalid_methods": 0,
            "unsafe_calls": 0,
            "forbidden_hits": 0,
            "failed_processes": 0,
        }
        reasons = runner.green_gate_reasons(summary, 0.8, 0.8)
        self.assertEqual(len(reasons), 1)
        self.assertIn("reference_read_rate", reasons[0])

    def test_reference_read_rate_is_reported_for_scoped_positive_cases(self):
        cases = [{
            "id": "scoped",
            "reference": "prefixes.md",
            "should_trigger": True,
            "complete": True,
            "majority_passed": False,
            "majority_activated": True,
            "majority_reference_read": False,
            "runs": [{
                "returncode": 0,
                "usage": {},
                "score": {
                    "invalid_methods": [],
                    "unsafe_calls": [],
                    "forbidden_hits": [],
                },
            }],
        }, {
            "id": "unscoped",
            "reference": None,
            "should_trigger": True,
            "complete": True,
            "majority_passed": True,
            "majority_activated": True,
            "majority_reference_read": None,
            "runs": [{
                "returncode": 0,
                "usage": {},
                "score": {
                    "invalid_methods": [],
                    "unsafe_calls": [],
                    "forbidden_hits": [],
                },
            }],
        }]
        summary = runner.summarize_phase(cases)
        self.assertEqual(summary["reference_cases"], 1)
        self.assertEqual(summary["reference_read_cases"], 0)
        self.assertEqual(summary["reference_read_rate"], 0.0)

    def test_policy_block_is_an_infrastructure_failure(self):
        cases = [{
            "should_trigger": True,
            "complete": False,
            "majority_passed": None,
            "majority_activated": None,
            "runs": [{
                "returncode": 0,
                "tool_policy_blocked": True,
                "usage": {},
                "score": {
                    "invalid_methods": [],
                    "unsafe_calls": [],
                    "forbidden_hits": [],
                },
            }],
        }]
        summary = runner.summarize_phase(cases)
        self.assertEqual(summary["cases"], 0)
        self.assertEqual(summary["attempted_cases"], 1)
        self.assertEqual(summary["failed_processes"], 1)
        self.assertEqual(summary["tool_policy_blocks"], 1)
        self.assertEqual(summary["infrastructure_failures"], 1)
        self.assertEqual(summary["infrastructure_reasons"], {"sandbox_policy": 1})
        self.assertEqual(summary["incomplete_runs"], 0)


class ResumeReportTests(unittest.TestCase):
    def test_resume_report_rejects_old_activation_semantics(self):
        report = {"schema_version": 2}
        with self.assertRaisesRegex(runner.EvalError, "schema_version=4"):
            runner.validate_resume_report(report, {})

    def test_resume_report_rejects_pre_encoding_check_semantics(self):
        with self.assertRaisesRegex(runner.EvalError, "schema_version=4"):
            runner.validate_resume_report({"schema_version": 3}, {})

    def test_resume_report_rejects_incompatible_model(self):
        report = {
            "schema_version": 4,
            "model": "old-model",
            "selected_cases": ["case-a"],
            "runs": 1,
            "phases_requested": ["red", "green"],
        }
        expected = {
            "model": "new-model",
            "selected_cases": ["case-a"],
            "runs": 1,
            "phases_requested": ["red", "green"],
        }
        with self.assertRaisesRegex(runner.EvalError, "model"):
            runner.validate_resume_report(report, expected)

    def test_resume_report_rejects_changed_runner(self):
        report = {"schema_version": 4, "runner_sha256": "old"}
        with self.assertRaisesRegex(runner.EvalError, "runner_sha256"):
            runner.validate_resume_report(report, {"runner_sha256": "new"})
        runner.validate_resume_report(report, {"runner_sha256": "old"})

    def test_atomic_report_write_replaces_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            path.write_text('{"old": true}', encoding="utf-8")
            runner.atomic_write_json(path, {"complete": False})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"complete": False})
            self.assertFalse(path.with_suffix(path.suffix + ".tmp").exists())


class ParallelExecutionTests(unittest.TestCase):
    @staticmethod
    def _case(case_id):
        return runner.EvalCase(
            id=case_id,
            task="test",
            reference=None,
            should_trigger=True,
            requires_bsl=False,
            required_patterns=(),
            forbidden_patterns=(),
            activation_patterns=(),
        )

    def test_run_matrix_is_concurrent_and_preserves_order(self):
        cases = [self._case("first"), self._case("second")]
        barrier = threading.Barrier(2)
        completed = []

        def execute(case, run_number):
            barrier.wait(timeout=2)
            return {"case": case.id, "run": run_number}

        def on_run_complete(case_index, run_index, _matrix):
            completed.append((case_index, run_index))

        matrix = runner.execute_run_matrix(
            cases, runs=2, jobs=2, execute=execute,
            on_run_complete=on_run_complete,
        )

        self.assertEqual(
            matrix,
            [
                [{"case": "first", "run": 1}, {"case": "first", "run": 2}],
                [{"case": "second", "run": 1}, {"case": "second", "run": 2}],
            ],
        )
        self.assertCountEqual(completed, [(0, 0), (0, 1), (1, 0), (1, 1)])

    def test_resume_keeps_completed_attempts_and_retries_only_retryable_slots(self):
        cases = [self._case("first")]
        completed = {"status": "completed", "marker": "keep"}
        quality_failed = {"status": "quality_failed", "marker": "keep-quality"}
        infrastructure_failed = {"status": "infrastructure_failed"}
        incomplete = {"status": "incomplete"}
        initial = runner.resume_run_matrix(
            cases,
            runs=5,
            stored={
                "first": [
                    completed,
                    infrastructure_failed,
                    quality_failed,
                    incomplete,
                ]
            },
        )
        executed = []

        def execute(case, run_number):
            executed.append((case.id, run_number))
            return {"status": "completed", "marker": "new"}

        matrix = runner.execute_run_matrix(
            cases, runs=5, jobs=1, execute=execute, initial_matrix=initial
        )

        self.assertEqual(executed, [("first", 2), ("first", 4), ("first", 5)])
        self.assertEqual(matrix[0][0]["marker"], "keep")
        self.assertEqual(matrix[0][1]["marker"], "new")
        self.assertEqual(matrix[0][2]["marker"], "keep-quality")
        self.assertEqual(matrix[0][3]["marker"], "new")
        self.assertEqual(matrix[0][4]["marker"], "new")

    def test_infrastructure_attempt_does_not_count_as_quality_result(self):
        cases = [self._case("first")]
        run = {
            "status": "infrastructure_failed",
            "score": {"passed": False},
            "skill_activated": False,
        }
        records = runner.phase_case_records(cases, [[run]], expected_runs=1)
        self.assertEqual(len(records), 1)
        self.assertFalse(records[0]["complete"])
        self.assertIsNone(records[0]["majority_passed"])

    def test_phase_records_skip_incomplete_cases(self):
        cases = [self._case("first"), self._case("second")]
        passing = {
            "score": {"passed": True},
            "skill_activated": True,
        }
        records = runner.phase_case_records(
            cases,
            [[passing, passing], [passing, None]],
            expected_runs=2,
        )
        self.assertEqual([record["id"] for record in records], ["first"])


if __name__ == "__main__":
    unittest.main()
