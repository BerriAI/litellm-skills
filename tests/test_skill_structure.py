"""Repo-wide checks that every skill is installable and follows the house rules."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIRS = sorted(p.parent for p in ROOT.glob("*/SKILL.md"))
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"

# Model ids that were retired or never existed; examples should not use them.
STALE_MODEL_IDS = [
    "claude-3-5-sonnet",
    "gemini-1.5-pro",
    "llama-3.3-70b-versatile",
    "gpt-5.5-mini",
]


def _frontmatter(text: str) -> dict:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    fields = {}
    current = None
    for line in match.group(1).splitlines():
        top = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if top:
            current = top.group(1)
            fields[current] = top.group(2).strip()
        elif current and line.startswith("  "):
            fields[current] = (fields[current] + " " + line.strip()).strip()
    return fields


class SkillStructureTest(unittest.TestCase):
    def test_there_are_skills(self):
        self.assertGreaterEqual(len(SKILL_DIRS), 10)

    def test_frontmatter(self):
        for skill_dir in SKILL_DIRS:
            with self.subTest(skill=skill_dir.name):
                fm = _frontmatter((skill_dir / "SKILL.md").read_text())
                self.assertEqual(fm.get("name"), skill_dir.name)
                self.assertTrue(skill_dir.name.startswith("litellm-"))
                description = fm.get("description", "").lstrip(">").strip()
                self.assertGreater(len(description), 150, "description too thin to trigger")
                self.assertLessEqual(len(description), 1024, "description over the 1024 char limit")
                self.assertIn("use", description.lower())
                self.assertIn("allowed-tools", fm)

    def test_skill_md_length(self):
        for skill_dir in SKILL_DIRS:
            with self.subTest(skill=skill_dir.name):
                lines = (skill_dir / "SKILL.md").read_text().count("\n")
                self.assertLess(lines, 500)

    def test_house_style(self):
        for path in ROOT.glob("*/**/*.md"):
            if "evals" in path.parts:
                continue
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text()
                self.assertNotIn("—", text, "em dash")
                self.assertNotIn("litellm.vercel.app", text, "old docs host")
                self.assertNotIn("$BASE/", text, "use $LITELLM_BASE_URL")
                for stale in STALE_MODEL_IDS:
                    self.assertNotIn(stale, text)

    def test_referenced_files_exist(self):
        for skill_dir in SKILL_DIRS:
            text = (skill_dir / "SKILL.md").read_text()
            for ref in set(re.findall(r"`((?:references|scripts)/[\w./-]+)`", text)):
                with self.subTest(skill=skill_dir.name, ref=ref):
                    self.assertTrue((skill_dir / ref).exists())

    def test_mcp_examples_never_use_hyphenated_server_names(self):
        for path in ROOT.glob("*/**/*.md"):
            for name in re.findall(r'"server_name":\s*"([^"]+)"', path.read_text()):
                with self.subTest(path=str(path.relative_to(ROOT)), name=name):
                    self.assertNotIn("-", name)

    def test_json_blocks_parse(self):
        for path in ROOT.glob("*/**/*.md"):
            for block in re.findall(r"```json\n(.*?)```", path.read_text(), re.S):
                if "<" in block or "..." in block:
                    continue  # placeholders
                with self.subTest(path=str(path.relative_to(ROOT))):
                    json.loads(block)

    def test_marketplace_lists_every_skill(self):
        data = json.loads(MARKETPLACE.read_text())
        listed = {Path(s).name for p in data["plugins"] for s in p.get("skills", [])}
        self.assertEqual(listed, {d.name for d in SKILL_DIRS})


if __name__ == "__main__":
    unittest.main()
