import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "litellm-budgets"
SKILL_MD = SKILL_DIR / "SKILL.md"
FIELDS_MD = SKILL_DIR / "references" / "fields.md"
SCRIPT = SKILL_DIR / "scripts" / "budget_check.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("budget_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Shapes follow the list endpoints in LiteLLM v1.103:
# /key/list?return_full_object=true -> {"keys": [...], "total_count", "current_page", "total_pages"}
KEYS_PAGE_1 = {
    "keys": [
        {"token": "a" * 64, "key_alias": "billing-agent-prod", "spend": 95.0, "max_budget": 100.0, "budget_duration": "30d", "budget_reset_at": "2026-10-01T00:00:00Z"},
        {"token": "b" * 64, "key_alias": "no-cap", "spend": 5000.0, "max_budget": None},
    ],
    "total_count": 3,
    "current_page": 1,
    "total_pages": 2,
}
KEYS_PAGE_2 = {
    "keys": [{"token": "c" * 64, "key_alias": "over", "spend": 12.0, "max_budget": 10.0}],
    "total_count": 3,
    "current_page": 2,
    "total_pages": 2,
}
# /user/list -> {"users": [...], "total", "page", "page_size", "total_pages"}
USERS = {"users": [{"user_id": "u1", "user_email": "ana@example.com", "spend": 2.0, "max_budget": 100.0}], "total": 1, "page": 1, "page_size": 100, "total_pages": 1}
# /v2/team/list -> {"teams": [...], "total", "page", "page_size", "total_pages"}
TEAMS = {"teams": [{"team_id": "t1", "team_alias": "search", "spend": 45.0, "max_budget": 100.0, "soft_budget": 40.0}], "total": 1, "page": 1, "page_size": 100, "total_pages": 1}
# /organization/list -> [LiteLLM_OrganizationTableWithMembers]
ORGS = [{"organization_id": "o1", "organization_alias": "acme", "spend": 0.0, "litellm_budget_table": {"max_budget": 0.0}}]
# /customer/list -> [CustomerResponse]
CUSTOMERS = [
    {"user_id": "acme-corp", "alias": "Acme Corp", "spend": 48.0, "blocked": False, "budget_id": "pro-tier", "litellm_budget_table": {"budget_id": "pro-tier", "max_budget": 50.0, "budget_duration": "1mo"}},
    {"user_id": "anon-123", "spend": 3.0, "blocked": False, "litellm_budget_table": None},
]
# /access_group/list -> {"access_groups": [AccessGroupInfo]}
ACCESS_GROUPS = {"access_groups": [{"access_group": "production-models", "model_names": ["gpt-5.5"], "deployment_count": 2, "spend": 510.0, "budget": {"budget_id": "x", "max_budget": 500.0, "budget_duration": "1mo"}}]}


class FakeProxy:
    def __init__(self):
        self.calls = []

    def __call__(self, path, params):
        self.calls.append((path, dict(params)))
        if path == "/key/list":
            return KEYS_PAGE_1 if params.get("page") == 1 else KEYS_PAGE_2
        return {
            "/user/list": USERS,
            "/v2/team/list": TEAMS,
            "/organization/list": ORGS,
            "/customer/list": CUSTOMERS,
            "/access_group/list": ACCESS_GROUPS,
        }[path]


class BudgetsSkillDocTest(unittest.TestCase):
    def setUp(self):
        self.text = SKILL_MD.read_text()

    def test_frontmatter_matches_template(self):
        self.assertTrue(self.text.startswith("---\nname: litellm-budgets\n"))
        self.assertIn("Written against LiteLLM v1.103 (September 2026).", self.text)
        self.assertIn('version: "2.0"', self.text)
        self.assertIn("allowed-tools: Bash(curl:*) Bash(python3:*)", self.text)
        self.assertLessEqual(len(self.text.splitlines()), 230)

    def test_covers_budget_crud_and_list_endpoints(self):
        for path in ("/budget/new", "/budget/update", "/budget/info", "/budget/delete", "/budget/list", "/management/v1/budgets"):
            self.assertIn(path, self.text)
        self.assertIn('{"id": "<budget_id>"}', self.text)  # BudgetDeleteRequest uses `id`, not `budget_id`

    def test_covers_customers_and_unblock_quirk(self):
        for path in ("/customer/new", "/customer/info?end_user_id=", "/customer/update", "/customer/delete", "/customer/block"):
            self.assertIn(path, self.text)
        self.assertIn('"blocked": false', self.text)
        self.assertIn("blocked_user_list", self.text)

    def test_warns_that_shared_tier_edits_fan_out(self):
        self.assertIn("every customer on the tier changes", " ".join(self.text.split()))

    def test_access_group_budget(self):
        self.assertIn("/access_group/production-models/budget", self.text)
        self.assertIn("v1.100+", self.text)

    def test_destructive_ops_require_confirmation(self):
        self.assertIn("explicit yes", self.text)

    def test_no_em_dashes(self):
        for path in (SKILL_MD, FIELDS_MD, SCRIPT):
            self.assertNotIn("—", path.read_text(), path.name)

    def test_uses_env_vars(self):
        self.assertIn("$LITELLM_BASE_URL", self.text)
        self.assertNotIn("$BASE/", self.text)


class BudgetCheckTest(unittest.TestCase):
    def setUp(self):
        self.m = _load_script()

    def _all_items(self, fake):
        items = []
        for kind in self.m.KINDS:
            items.extend(self.m.normalize(kind, o) for o in self.m.fetch(kind, fake))
        return items

    def test_fetch_pages_key_list(self):
        fake = FakeProxy()
        keys = self.m.fetch("keys", fake)
        self.assertEqual(len(keys), 3)
        key_calls = [c for c in fake.calls if c[0] == "/key/list"]
        self.assertEqual([c[1]["page"] for c in key_calls], [1, 2])
        self.assertEqual(key_calls[0][1]["return_full_object"], "true")

    def test_evaluate_flags_over_near_soft(self):
        flagged = self.m.evaluate(self._all_items(FakeProxy()), threshold=0.8)
        by_label = {r["label"]: r for r in flagged}
        self.assertEqual(by_label["over"]["status"], "over")
        self.assertEqual(by_label["billing-agent-prod"]["status"], "near")
        self.assertEqual(by_label["Acme Corp"]["status"], "near")
        self.assertEqual(by_label["production-models"]["status"], "over")
        self.assertEqual(by_label["search"]["status"], "soft")  # 45 of 100, past soft_budget 40
        self.assertEqual(by_label["acme"]["status"], "over")  # max_budget 0 = no allowance
        self.assertNotIn("no-cap", by_label)  # no max_budget
        self.assertNotIn("ana@example.com", by_label)  # 2%
        self.assertNotIn("anon-123", by_label)  # no own budget
        statuses = [r["status"] for r in flagged]
        self.assertEqual(statuses, sorted(statuses, key={"over": 0, "near": 1, "soft": 2}.get))

    def test_threshold_changes_near(self):
        items = [self.m.normalize("teams", {"team_id": "t", "spend": 60, "max_budget": 100})]
        self.assertEqual(self.m.evaluate(items, 0.8), [])
        self.assertEqual(self.m.evaluate(items, 0.5)[0]["status"], "near")

    def test_normalize_is_robust_to_missing_fields(self):
        for kind in self.m.KINDS:
            item = self.m.normalize(kind, {})
            self.assertEqual(item["spend"], 0.0)
            self.assertIsNone(item["max_budget"])
        self.assertEqual(self.m.evaluate([self.m.normalize("keys", {"spend": "abc", "max_budget": "10"})]), [])

    def test_render_text(self):
        flagged = self.m.evaluate(self._all_items(FakeProxy()))
        text = self.m.render_text(flagged, 0.8, {"keys": 3})
        self.assertIn("over", text)
        self.assertIn("billing-agent-prod", text)
        self.assertIn("Nothing is near or over budget.", self.m.render_text([], 0.8, {}))


if __name__ == "__main__":
    unittest.main()
