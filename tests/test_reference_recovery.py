"""Regression for a project BSP reference resolved from another system skill."""
import json
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ci import run_skill_evals as runner

ROOT = Path(__file__).resolve().parents[1]


class ReferenceRecoveryTests(unittest.TestCase):
    def test_router_prioritizes_explicit_api_review_without_widening_platform_scope(self):
        text = (ROOT / "skills/bsp/SKILL.md").read_text(encoding="ascii")
        description = json.loads(next(line.removeprefix("description: ")
                                      for line in text.splitlines() if line.startswith("description: ")))
        self.assertIn("Explicit BSP API review, including method existence", description)
        self.assertIn("platform-only exclusion applies only without BSP API review", description)
        scope = " ".join(text.split("Scope precedence:", 1)[1].split("1. Check", 1)[0].split())
        self.assertIn("requires the selected reference even when the recommendation uses platform APIs", scope)
        self.assertIn("Apply the version boundary below first", scope)
        self.assertIn("Standalone platform-only requests without BSP API review are outside", scope)
        for corpus_id in ("exchange-register-changes", "neutral-platform-exchange-registration",
                          "neutral-form-caption", "connected-command-hook-boundary"):
            self.assertNotIn(corpus_id, text)

    def test_failed_system_path_and_listing_do_not_prove_reference_read(self):
        events = [{"type": "item.completed", "item": {
            "type": "command_execution", "exit_code": 0,
            "command": "rg -n . C:/consumer/.agents/skills/bsp/SKILL.md; rg --files",
            "aggregated_output": "1:name: bsp\nREADME.md",
        }}, {"type": "item.completed", "item": {
            "type": "command_execution", "exit_code": 1,
            "command": "rg -n command C:/private/skills/.system/imagegen/../bsp/references/commands-external.md",
            "aggregated_output": "rg: C:/private/skills/.system/imagegen/../bsp/references/commands-external.md: os error 3",
        }}, {"type": "item.completed", "item": {
            "type": "command_execution", "exit_code": 0,
            "command": "rg --files C:/private/skills; rg --files C:/consumer",
            "aggregated_output": "C:/consumer/README.md",
        }}]
        self.assertTrue(runner.skill_activation_evidence(events, "bsp"))
        self.assertEqual(runner.skill_activation_evidence(events, "bsp", "commands-external.md"), [])
        # The two other repetitions may satisfy the majority; this run still did not read.
        self.assertTrue(runner.majority([True, False, True]))
        self.assertFalse(runner.majority([False]))

    def fallback_command(self, skill, reference):
        router = (ROOT / "skills/bsp/SKILL.md").read_text(encoding="ascii")
        section = router.split("## Reference fallback", 1)[1].split("## Task routing", 1)[0]
        command = re.search(r"```bash\n([^\n]+)\n```", section).group(1)
        arguments = shlex.split(command)
        arguments[0] = sys.executable
        arguments[-1] = arguments[-1].replace("ABSOLUTE_SKILL_MD", skill.as_posix()).replace("REFERENCE.md", reference)
        return arguments

    def test_documented_fallback_uses_opened_skill_not_cwd_or_system_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed = root / "consumer with spaces/.agents/skills/bsp"
            installed.mkdir(parents=True)
            skill = installed / "SKILL.md"
            skill.write_text("name: bsp", encoding="ascii")
            (installed / "references").mkdir()
            name = "команды with spaces.md"
            content = "# Подключаемые команды\nПравильный установленный reference.\n"
            (installed / "references" / name).write_text(content, encoding="utf-8")
            system = root / "private/skills/.system/imagegen"
            system.mkdir(parents=True)
            wrong = system.parent / "bsp/references"
            wrong.mkdir(parents=True)
            (wrong / name).write_text("WRONG ROOT", encoding="ascii")
            result = subprocess.run(self.fallback_command(skill, name), cwd=system,
                                    capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), content.strip())
            self.assertEqual(runner.python_reader_targets(self.fallback_command(skill, name)),
                             [(installed / "references" / name).as_posix()])
            missing = subprocess.run(self.fallback_command(skill, "missing.md"), cwd=system,
                                     capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("FileNotFoundError", missing.stderr)


if __name__ == "__main__":
    unittest.main()
