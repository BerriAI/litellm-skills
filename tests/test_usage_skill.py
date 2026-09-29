import argparse
import contextlib
import importlib.util
import io
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "litellm-usage"
SKILL_MD = SKILL_DIR / "SKILL.md"
ENDPOINTS_MD = SKILL_DIR / "references" / "endpoints.md"
SCRIPT = SKILL_DIR / "scripts" / "usage_report.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("usage_report", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metrics(spend=0.0, requests=0, failed=0, tokens=0):
    """SpendMetrics-shaped dict (litellm/types/proxy/management_endpoints/common_daily_activity.py)."""
    return {
        "spend": spend,
        "flat_cost": 0.0,
        "prompt_tokens": tokens,
        "completion_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "compression_saved_tokens": 0,
        "compression_savings_spend": 0.0,
        "prompt_caching_savings_spend": 0.0,
        "gateway_injected_caching_savings_spend": 0.0,
        "autorouter_savings_spend": 0.0,
        "total_tokens": tokens,
        "successful_requests": requests - failed,
        "failed_requests": failed,
        "api_requests": requests,
        "total_response_time_ms": 0,
        "timed_requests": 0,
    }


def _metadata(page, total_pages, has_more, page_spend=0.0):
    """DailySpendMetadata-shaped dict: page totals plus page/total_pages/has_more, no page_size/total_count."""
    return {
        "total_spend": page_spend,
        "total_flat_cost": 0.0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_tokens": 0,
        "total_api_requests": 0,
        "total_successful_requests": 0,
        "total_failed_requests": 0,
        "total_cache_read_input_tokens": 0,
        "total_cache_creation_input_tokens": 0,
        "total_compression_saved_tokens": 0,
        "total_compression_savings_spend": 0.0,
        "total_prompt_caching_savings_spend": 0.0,
        "total_gateway_injected_caching_savings_spend": 0.0,
        "total_autorouter_savings_spend": 0.0,
        "total_response_time_ms": 0,
        "total_timed_requests": 0,
        "page": page,
        "total_pages": total_pages,
        "has_more": has_more,
    }


def _day(date, spend, requests, failed=0, tokens=0, models=None, api_keys=None, entities=None):
    return {
        "date": date,
        "metrics": _metrics(spend, requests, failed, tokens),
        "breakdown": {
            "mcp_servers": {},
            "models": {name: {"metrics": _metrics(*vals), "metadata": {}, "api_key_breakdown": {}} for name, vals in (models or {}).items()},
            "model_groups": {},
            "providers": {},
            "endpoints": {},
            "api_keys": {
                name: {"metrics": _metrics(*vals), "metadata": {"key_alias": alias, "team_id": None, "user_id": None, "user_email": None, "key_exists": True}}
                for name, (alias, vals) in (api_keys or {}).items()
            },
            "entities": {
                name: {"metrics": _metrics(*vals), "metadata": meta, "api_key_breakdown": {}}
                for name, (meta, vals) in (entities or {}).items()
            },
        },
    }


# Page 1 and page 2 both contain 2026-09-02: pagination is over DB rows, not days.
PAGE_1 = {
    "results": [
        _day("2026-09-02", 3.0, 30, failed=2, tokens=3000, models={"gpt-5.5": (3.0, 30, 2, 3000)},
             entities={"team-a": ({"team_alias": "search"}, (3.0, 30, 2, 3000))}),
        _day("2026-09-01", 1.0, 10, tokens=1000, models={"claude-sonnet-5-5": (1.0, 10, 0, 1000)},
             entities={"team-a": ({"team_alias": "search"}, (1.0, 10, 0, 1000))}),
    ],
    "metadata": _metadata(1, 2, True, page_spend=4.0),
}
PAGE_2 = {
    "results": [
        _day("2026-09-02", 2.0, 5, tokens=500, models={"gpt-5.5": (2.0, 5, 0, 500)},
             entities={"team-b": ({"team_alias": "billing"}, (2.0, 5, 0, 500))}),
    ],
    "metadata": _metadata(2, 2, False, page_spend=2.0),
}
AGGREGATED = {
    "results": [
        _day("2026-09-01", 1.5, 12, tokens=1200,
             api_keys={"a" * 64: ("billing-agent-prod", (1.0, 8, 0, 800)), "b" * 64: (None, (0.5, 4, 0, 400))}),
    ],
    "metadata": _metadata(1, 1, False, page_spend=1.5),
}


class FakeProxy:
    """Records calls and serves canned responses per path."""

    def __init__(self, pages_by_path):
        self.pages_by_path = pages_by_path
        self.calls = []

    def __call__(self, path, params):
        self.calls.append((path, dict(params)))
        served = self.pages_by_path[path]
        if isinstance(served, Exception):
            raise served
        if isinstance(served, list):
            return served[int(params.get("page", 1)) - 1]
        return served


def _args(**overrides):
    base = dict(by="overall", ids=None, start="2026-09-01", end="2026-09-28", model=None, key_hash=None, top="", limit=10, json=False)
    base.update(overrides)
    return argparse.Namespace(**base)


class UsageSkillDocTest(unittest.TestCase):
    def setUp(self):
        self.text = SKILL_MD.read_text()

    def test_frontmatter_matches_template(self):
        self.assertTrue(self.text.startswith("---\nname: litellm-usage\n"))
        self.assertIn("license: MIT", self.text)
        self.assertIn("Written against LiteLLM v1.103 (September 2026).", self.text)
        self.assertIn('version: "2.0"', self.text)
        self.assertIn("allowed-tools: Bash(curl:*) Bash(python3:*)", self.text)
        self.assertLessEqual(len(self.text.splitlines()), 230)

    def test_uses_env_vars_not_placeholders(self):
        self.assertIn("$LITELLM_BASE_URL", self.text)
        self.assertIn("$LITELLM_API_KEY", self.text)
        self.assertNotIn("$BASE/", self.text)
        self.assertNotIn("$KEY\"", self.text)

    def test_mentions_aggregated_endpoints(self):
        self.assertIn("/user/daily/activity/aggregated", self.text)
        self.assertIn("/team/daily/activity/aggregated", self.text)

    def test_paginates_on_has_more(self):
        self.assertIn("has_more", self.text)
        self.assertRegex(self.text, r"not over days|not days")
        self.assertRegex(self.text.lower(), r"merge .*by `?date`?")

    def test_does_not_claim_page_size_or_total_count_in_metadata(self):
        # The old skill documented {"page_size": 10, "total_count": 31}; DailySpendMetadata has neither.
        self.assertNotRegex(self.text, r'"metadata":\s*\{[^}]*"(page_size|total_count)"')
        flat = " ".join(self.text.split())
        self.assertIn("There is no `page_size` or `total_count`", flat)

    def test_requires_start_and_end_date(self):
        self.assertIn("start_date", self.text)
        self.assertIn("end_date", self.text)
        self.assertRegex(self.text, r"required.*400|400.*start_date and end_date")

    def test_documents_tag_double_counting_and_top_tags(self):
        self.assertIn("/tag/daily/activity", self.text)
        self.assertIn("/global/spend/tags", self.text)
        self.assertIn("spend_per_tag", self.text)
        self.assertIn("double count", self.text)

    def test_does_not_recommend_hidden_global_activity(self):
        self.assertNotIn("/global/activity?", self.text)
        self.assertIn("/global/activity", ENDPOINTS_MD.read_text())

    def test_uses_live_docs_anchor(self):
        self.assertIn("docs/proxy/cost_tracking#daily-spend-breakdown-api", self.text)
        self.assertNotIn("users#get-user-spend", self.text)

    def test_no_em_dashes(self):
        for path in (SKILL_MD, ENDPOINTS_MD, SCRIPT):
            self.assertNotIn("—", path.read_text(), path.name)

    def test_request_logs_use_v2(self):
        self.assertIn("/spend/logs/v2", self.text)


class PlanRequestsTest(unittest.TestCase):
    def setUp(self):
        self.m = _load_script()

    def test_overall_prefers_user_aggregated(self):
        plans = self.m.plan_requests("overall", [], "2026-09-01", "2026-09-28")
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["path"], "/user/daily/activity/aggregated")
        self.assertFalse(plans[0]["paginated"])
        self.assertEqual(plans[0]["params"], {"start_date": "2026-09-01", "end_date": "2026-09-28"})

    def test_user_id_is_singular_so_one_call_per_user(self):
        plans = self.m.plan_requests("user", ["u1", "u2"], "2026-09-01", "2026-09-28")
        self.assertEqual([p["params"]["user_id"] for p in plans], ["u1", "u2"])
        self.assertEqual([p["entity"] for p in plans], ["u1", "u2"])

    def test_plural_id_params(self):
        expected = {"team": "team_ids", "org": "organization_ids", "tag": "tags", "customer": "end_user_ids", "agent": "agent_ids"}
        for by, param in expected.items():
            plans = self.m.plan_requests(by, ["x", "y"], "2026-09-01", "2026-09-28")
            self.assertEqual(len(plans), 1, by)
            self.assertEqual(plans[0]["params"][param], "x,y", by)

    def test_endpoints_without_aggregated_variant_paginate(self):
        paths = {
            "org": "/organization/daily/activity",
            "tag": "/tag/daily/activity",
            "customer": "/customer/daily/activity",
            "agent": "/agent/daily/activity",
        }
        for by, path in paths.items():
            plan = self.m.plan_requests(by, [], "2026-09-01", "2026-09-28")[0]
            self.assertEqual(plan["path"], path)
            self.assertTrue(plan["paginated"])
            self.assertLessEqual(plan["params"]["page_size"], 1000)

    def test_team_aggregated_respects_400_day_cap(self):
        plan = self.m.plan_requests("team", ["t"], "2025-01-01", "2026-09-01")[0]
        self.assertEqual(plan["path"], "/team/daily/activity")
        plan = self.m.plan_requests("team", ["t"], "2026-01-01", "2026-09-01")[0]
        self.assertEqual(plan["path"], "/team/daily/activity/aggregated")

    def test_entities_for_all_users_needs_paginated_endpoint(self):
        plan = self.m.plan_requests("user", [], "2026-09-01", "2026-09-28", need_entities=True)[0]
        self.assertEqual(plan["path"], "/user/daily/activity")
        team_plan = self.m.plan_requests("team", [], "2026-09-01", "2026-09-28", need_entities=True)[0]
        self.assertEqual(team_plan["path"], "/team/daily/activity/aggregated")

    def test_filters_forwarded(self):
        plan = self.m.plan_requests("tag", ["job:nightly-eval"], "2026-09-01", "2026-09-28", model="gpt-5.5", key_hash="abc")[0]
        self.assertEqual(plan["params"]["model"], "gpt-5.5")
        self.assertEqual(plan["params"]["api_key"], "abc")

    def test_default_range_is_current_month(self):
        import datetime

        self.assertEqual(self.m.default_range(datetime.date(2026, 9, 29)), ("2026-09-01", "2026-09-29"))


class FetchAndAggregateTest(unittest.TestCase):
    def setUp(self):
        self.m = _load_script()

    def test_pages_until_has_more_false(self):
        fake = FakeProxy({"/tag/daily/activity": [PAGE_1, PAGE_2]})
        plan = self.m.plan_requests("tag", ["job:nightly-eval"], "2026-09-01", "2026-09-28")[0]
        rows = self.m.fetch_all(fake, plan)
        self.assertEqual([c[1]["page"] for c in fake.calls], [1, 2])
        self.assertEqual(len(rows), 3)

    def test_stops_on_empty_page_even_if_has_more(self):
        stuck = {"results": [], "metadata": _metadata(1, 5, True)}
        fake = FakeProxy({"/tag/daily/activity": [stuck]})
        plan = self.m.plan_requests("tag", [], "2026-09-01", "2026-09-28")[0]
        self.assertEqual(self.m.fetch_all(fake, plan), [])
        self.assertEqual(len(fake.calls), 1)

    def test_merges_same_date_across_pages_and_ignores_page_totals(self):
        days = self.m.merge_days(PAGE_1["results"] + PAGE_2["results"])
        rows = self.m.day_rows(days)
        self.assertEqual([r["date"] for r in rows], ["2026-09-01", "2026-09-02"])
        sep2 = rows[1]
        self.assertAlmostEqual(sep2["spend"], 5.0)
        self.assertEqual(sep2["api_requests"], 35)
        total = self.m.totals(rows)
        self.assertAlmostEqual(total["spend"], 6.0)  # not metadata.total_spend of either page
        self.assertEqual(total["failed_requests"], 2)
        self.assertEqual([r["date"] for r in self.m.failed_days(rows)], ["2026-09-02"])

    def test_top_models_and_entities(self):
        days = self.m.merge_days(PAGE_1["results"] + PAGE_2["results"])
        models = self.m.top_n(days, "models", 5)
        self.assertEqual(models[0]["name"], "gpt-5.5")
        self.assertAlmostEqual(models[0]["spend"], 5.0)
        entities = self.m.top_n(days, "entities", 5)
        self.assertEqual(entities[0]["name"], "team-a")
        self.assertIn("search", entities[0]["label"])

    def test_top_api_keys_use_alias(self):
        days = self.m.merge_days(AGGREGATED["results"])
        keys = self.m.top_n(days, "api_keys", 1)
        self.assertEqual(len(keys), 1)
        self.assertTrue(keys[0]["label"].startswith("billing-agent-prod"))

    def test_robust_to_missing_fields(self):
        rows = [{"date": "2026-09-03"}, {"date": "2026-09-03", "metrics": {"spend": None, "api_requests": "7"}, "breakdown": None}, {}]
        days = self.m.merge_days(rows)
        table = self.m.day_rows(days)
        self.assertEqual(len(table), 2)
        self.assertEqual(self.m.top_n(days, "mcp_servers", 3), [])
        self.m.render_text(self.m.build_report("overall", "2026-09-01", "2026-09-28", days, [{"path": "/x", "paginated": False}], [], ["mcp_servers"], 3))

    def test_run_uses_aggregated_and_renders(self):
        fake = FakeProxy({"/user/daily/activity/aggregated": AGGREGATED})
        report = self.m.run(_args(top="api_keys"), fake)
        self.assertEqual(fake.calls[0][0], "/user/daily/activity/aggregated")
        self.assertNotIn("page", fake.calls[0][1])
        self.assertAlmostEqual(report["totals"]["spend"], 1.5)
        text = self.m.render_text(report)
        self.assertRegex(text, r"Date\s+Requests\s+Tokens\s+Spend")
        self.assertIn("TOTAL", text)

    def test_run_falls_back_to_paginated_on_404(self):
        m = self.m
        fake = FakeProxy({"/user/daily/activity/aggregated": m.HttpError(404, "Not Found", "/x"), "/user/daily/activity": [PAGE_1, PAGE_2]})
        report = m.run(_args(), fake)
        self.assertEqual([c[0] for c in fake.calls], ["/user/daily/activity/aggregated", "/user/daily/activity", "/user/daily/activity"])
        self.assertAlmostEqual(report["totals"]["spend"], 6.0)

    def test_run_labels_each_user_when_looping(self):
        fake = FakeProxy({"/user/daily/activity/aggregated": AGGREGATED})
        report = self.m.run(_args(by="user", ids="alice,bob", top="entities"), fake)
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual({e["name"] for e in report["top"]["entities"]}, {"alice", "bob"})
        self.assertAlmostEqual(report["totals"]["spend"], 3.0)

    def test_tag_report_warns_about_double_counting(self):
        fake = FakeProxy({"/tag/daily/activity": [PAGE_1, PAGE_2]})
        report = self.m.run(_args(by="tag"), fake)
        self.assertTrue(any("double count" in w for w in report["warnings"]))

    def test_rejects_unknown_top_dimension(self):
        with self.assertRaises(ValueError):
            self.m.run(_args(top="users"), FakeProxy({}))

    def test_main_requires_credentials(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = self.m.main(["--base-url", "", "--api-key", ""])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
