"""Keep the skill's first read safe before any UTF-8 guidance is available."""
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "bsp"


class SkillBootstrapTests(unittest.TestCase):
    def test_router_is_ascii_before_reader_guidance_is_loaded(self):
        self.assertTrue((SKILL / "SKILL.md").read_bytes().isascii())

    def test_router_routes_to_every_shipped_reference(self):
        router = (SKILL / "SKILL.md").read_text(encoding="ascii")
        routed = set(re.findall(r"`references/([a-z][a-z-]+\.md)`", router))
        shipped = {path.name for path in (SKILL / "references").glob("*.md")}
        self.assertEqual(routed, shipped)


if __name__ == "__main__":
    unittest.main()
