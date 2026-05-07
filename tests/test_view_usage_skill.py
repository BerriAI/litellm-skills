import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEW_USAGE_SKILL = ROOT / "view-usage" / "SKILL.md"


def _skill_text() -> str:
    return VIEW_USAGE_SKILL.read_text()


class ViewUsageSkillTest(unittest.TestCase):
    def test_documents_global_cost_api(self):
        text = _skill_text()

        self.assertIn("/global/activity", text)
        self.assertTrue(
            "overall cost" in text.lower() or "overall spend" in text.lower()
        )

    def test_documents_tag_and_job_cost_attribution(self):
        text = _skill_text()

        self.assertIn("/tag/daily/activity", text)
        self.assertIn("tags=<tag>", text)
        self.assertIn("job", text.lower())
        self.assertTrue("tag by job" in text.lower() or "job:" in text.lower())

    def test_documents_top_tag_spend_api(self):
        text = _skill_text()

        self.assertIn("/global/spend/tags", text)


if __name__ == "__main__":
    unittest.main()
