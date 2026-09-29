import contextlib
import datetime as dt
import importlib.util
import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "litellm-doctor"
SCRIPT = SKILL_DIR / "scripts" / "doctor.py"
NOW = dt.datetime(2026, 9, 29, 12, 0, tzinfo=dt.timezone.utc)


def _load_script():
    spec = importlib.util.spec_from_file_location("litellm_doctor", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


doctor = _load_script()


def _levels(findings):
    return [level for level, _ in findings]


class NormalizeAndParseTest(unittest.TestCase):
    def test_normalize_base_url(self):
        self.assertEqual(doctor.normalize_base_url(" https://llm.acme.com/ "), "https://llm.acme.com")
        self.assertEqual(doctor.normalize_base_url("localhost:4000"), "http://localhost:4000")
        self.assertEqual(doctor.normalize_base_url(""), "")

    def test_parse_time_handles_z_naive_and_junk(self):
        self.assertEqual(doctor.parse_time("2026-09-01T00:00:00Z"), dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc))
        self.assertEqual(doctor.parse_time("2026-09-01T00:00:00").tzinfo, dt.timezone.utc)
        self.assertIsNone(doctor.parse_time("not a date"))
        self.assertIsNone(doctor.parse_time(None))

    def test_error_text_reads_proxy_and_fastapi_shapes(self):
        self.assertEqual(doctor.error_text({"error": {"message": "boom", "type": "auth_error"}}), "boom")
        self.assertEqual(doctor.error_text({"detail": {"error": "nope"}}), "nope")
        self.assertEqual(doctor.error_text({"detail": "plain"}), "plain")
        self.assertEqual(doctor.error_type({"error": {"type": "budget_exceeded"}}), "budget_exceeded")


class ClassifyFailureTest(unittest.TestCase):
    def test_budget_is_recognized_by_type_or_message_not_status(self):
        for status in (422, 429, 400):
            self.assertIn("Budget exceeded", doctor.classify_failure(status, "", "budget_exceeded"))
        self.assertIn("Budget exceeded", doctor.classify_failure(422, "Budget has been exceeded! Key=..."))

    def test_401_variants(self):
        self.assertIn("expired", doctor.classify_failure(401, "Authentication Error - Expired Key. Key Expiry time").lower())
        self.assertIn("blocked", doctor.classify_failure(401, "Key is blocked. Update via `/key/unblock`").lower())
        self.assertIn("admin", doctor.classify_failure(401, "Only proxy admin can be used to generate, delete").lower())
        self.assertIn("not recognized", doctor.classify_failure(401, "Invalid proxy server token passed"))

    def test_403_model_access_vs_route(self):
        self.assertIn("allowed models", doctor.classify_failure(403, "", "key_model_access_denied"))
        self.assertIn("allowed_routes", doctor.classify_failure(403, "Virtual key is not allowed to call this route."))

    def test_invalid_model_name_is_a_400(self):
        msg = "/chat/completions: Invalid model name passed in model=gpt-9. Call `/v1/models`"
        self.assertIn("not on the proxy", doctor.classify_failure(400, msg))

    def test_429_proxy_vs_provider(self):
        self.assertIn("Proxy rpm/tpm", doctor.classify_failure(429, "Rate limit exceeded for api_key: abc. Limit type: requests."))
        self.assertIn("Provider rate limit", doctor.classify_failure(429, "", rate_limit_category="vendor_rate_limit"))

    def test_5xx_db_vs_provider_and_unreachable(self):
        self.assertIn("Database", doctor.classify_failure(503, "", "no_db_connection"))
        self.assertIn("provider", doctor.classify_failure(500, "litellm.InternalServerError: AnthropicException").lower())
        self.assertIn("reach", doctor.classify_failure(None))


class ModelAllowedTest(unittest.TestCase):
    def test_empty_wildcards_and_all_proxy_models(self):
        self.assertEqual(doctor.model_allowed([], "gpt-5.5"), "yes")
        self.assertEqual(doctor.model_allowed(["all-proxy-models"], "gpt-5.5"), "yes")
        self.assertEqual(doctor.model_allowed(["claude-*"], "claude-sonnet-5-5"), "yes")

    def test_unknown_entries_may_be_access_groups(self):
        known = ["gpt-5.5", "claude-sonnet-5-5", "gemini-3.5-flash"]
        self.assertEqual(doctor.model_allowed(["gpt-5.5"], "claude-sonnet-5-5", known), "no")
        self.assertEqual(doctor.model_allowed(["research-models"], "claude-sonnet-5-5", known), "maybe")
        self.assertEqual(doctor.model_allowed(["gpt-5.5"], "claude-sonnet-5-5"), "maybe")


class SummarizeKeyTest(unittest.TestCase):
    def test_healthy_key(self):
        info = {"key_alias": "billing-agent-prod", "spend": 1.0, "max_budget": 50, "models": [], "expires": None}
        findings = doctor.summarize_key(info, now=NOW)
        self.assertEqual(findings[0][0], doctor.OK)
        self.assertNotIn(doctor.FAIL, _levels(findings))

    def test_blocked_expired_over_budget_and_model(self):
        info = {
            "key_alias": "marketing-bot",
            "blocked": True,
            "expires": "2026-09-01T00:00:00+00:00",
            "spend": 60.0,
            "max_budget": 50,
            "models": ["gpt-5.5"],
            "key_type": "llm_api",
            "team_id": "team-marketing",
        }
        findings = doctor.summarize_key(info, now=NOW, model="claude-sonnet-5-5", known_models=["gpt-5.5", "claude-sonnet-5-5"])
        text = " ".join(detail for _, detail in findings)
        self.assertEqual(_levels(findings).count(doctor.FAIL), 4)
        self.assertIn("blocked", text)
        self.assertIn("expired", text)
        self.assertIn("over budget", text)
        self.assertIn("claude-sonnet-5-5 is not in", text)
        self.assertIn("llm_api", text)

    def test_budget_warning_and_expiry_soon(self):
        info = {"key_alias": "k", "spend": 45, "max_budget": 50, "expires": "2026-10-02T00:00:00Z"}
        self.assertEqual(_levels(doctor.summarize_key(info, now=NOW)).count(doctor.WARN), 2)


class SummarizeFailuresTest(unittest.TestCase):
    def _row(self, code, klass, group, msg="", category=None, request_id="r"):
        info = {"error_code": code, "error_class": klass, "error_message": msg, "llm_provider": "openai"}
        if category:
            info["error_rate_limit_category"] = category
        return {"request_id": request_id, "model_group": group, "status": "failure", "metadata": {"error_information": info}}

    def test_groups_rank_and_classify(self):
        rows = [
            self._row("429", "RateLimitError", "gpt-5.5", "Rate limit exceeded for api_key: x", "litellm_rate_limit", "a"),
            self._row("429", "RateLimitError", "gpt-5.5", "Rate limit exceeded for api_key: x", "litellm_rate_limit", "b"),
            self._row("500", "InternalServerError", "claude-sonnet-5-5", "AnthropicException - overloaded"),
            {"not": "a row with metadata"},
            "junk",
        ]
        groups = doctor.summarize_failures(rows)
        self.assertEqual(groups[0]["count"], 2)
        self.assertEqual(groups[0]["model_group"], "gpt-5.5")
        self.assertIn("Proxy rpm/tpm", groups[0]["likely_cause"])
        self.assertEqual(groups[0]["last_request_id"], "a")
        self.assertIn("provider", groups[1]["likely_cause"].lower())
        self.assertEqual(len(groups), 3)

    def test_empty(self):
        self.assertEqual(doctor.summarize_failures([]), [])
        self.assertEqual(doctor.summarize_failures(None), [])


class SummarizeHealthAndReadinessTest(unittest.TestCase):
    def test_health(self):
        payload = {
            "healthy_endpoints": [{"model": "openai/gpt-5.5"}],
            "unhealthy_endpoints": [{"model": "anthropic/claude-sonnet-5-5", "error": "AuthenticationError: invalid x-api-key\nstack"}],
        }
        findings = doctor.summarize_health(payload)
        self.assertEqual(findings[0][0], doctor.WARN)
        self.assertIn("invalid x-api-key", findings[1][1])
        self.assertNotIn("stack", findings[1][1])
        self.assertEqual(doctor.summarize_health({})[0][0], doctor.WARN)
        self.assertEqual(doctor.summarize_health({"unhealthy_endpoints": [{"model": "m"}]})[0][0], doctor.FAIL)

    def test_readiness(self):
        self.assertEqual(_levels(doctor.summarize_readiness({"status": "healthy", "db": "connected"})), [doctor.OK, doctor.OK])
        self.assertIn(doctor.FAIL, _levels(doctor.summarize_readiness({"status": "healthy", "db": "disconnected"})))
        self.assertIn(doctor.WARN, _levels(doctor.summarize_readiness({"status": "healthy", "db": "Not connected"})))
        self.assertIn(doctor.WARN, _levels(doctor.summarize_readiness({"status": "healthy", "db": "connected", "is_detailed_debug": True})))


class RenderAndCliTest(unittest.TestCase):
    def test_render_counts(self):
        report = {"base_url": "http://x", "litellm_version": "1.103.0", "checks": [
            {"check": "a", "level": doctor.OK, "detail": "fine"},
            {"check": "b", "level": doctor.FAIL, "detail": "bad"},
        ]}
        out = doctor.render(report)
        self.assertIn("version=1.103.0", out)
        self.assertIn("[FAIL] b: bad", out)
        self.assertIn("1 fail, 0 warn, 1 ok", out)

    def test_missing_base_url_is_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(doctor.main(["--base-url", "", "--api-key", "sk-test"]), 2)


class SkillDocTest(unittest.TestCase):
    def test_skill_md_points_at_script_and_key_endpoints(self):
        text = (SKILL_DIR / "SKILL.md").read_text()
        self.assertIn("scripts/doctor.py", text)
        for endpoint in ("/health/liveliness", "/health/readiness/details", "/key/info", "/spend/logs/v2", "/health?model="):
            self.assertIn(endpoint, text)
        self.assertNotIn("\u2014", text)


if __name__ == "__main__":
    unittest.main()
