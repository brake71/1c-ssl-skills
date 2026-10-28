"""Keep the skill's first read safe before any UTF-8 guidance is available."""
import json
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "bsp"


class SkillBootstrapTests(unittest.TestCase):
    def test_router_is_ascii_before_reader_guidance_is_loaded(self):
        self.assertTrue((SKILL / "SKILL.md").read_bytes().isascii())

    def test_neutral_export_review_has_a_scope_pointer_without_platform_activation(self):
        router = (SKILL / "SKILL.md").read_text(encoding="ascii")
        description = json.loads(router.split("description: ", 1)[1].splitlines()[0])
        for cue in ("standard subsystems", "exported common module", "ВызовСервера",
                    "СлужебныйПрограммныйИнтерфейс", "fundamentals.md"):
            with self.subTest(cue=cue):
                self.assertIn(cue, description)
        self.assertIn("platform-only exchange", description)

    def test_router_routes_to_every_shipped_reference(self):
        router = (SKILL / "SKILL.md").read_text(encoding="ascii")
        routed = set(re.findall(r"`references/([a-z][a-z-]+\.md)`", router))
        shipped = {path.name for path in (SKILL / "references").glob("*.md")}
        self.assertEqual(routed, shipped)


if __name__ == "__main__":
    unittest.main()
