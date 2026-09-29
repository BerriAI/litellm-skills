"""Live smoke test: run the requests the skills document against a real proxy.

Point it at a DISPOSABLE proxy (it creates and deletes keys, users, teams,
models, MCP servers, agents, guardrails, budgets, and customers):

    LITELLM_BASE_URL=http://localhost:4100 LITELLM_API_KEY=<master key> \
        python3 tests/live_smoke.py

Models are registered with `mock_response`, so no provider keys are needed and
no real LLM calls are made. Exit code is the number of failed checks.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = os.environ["LITELLM_BASE_URL"].rstrip("/")
KEY = os.environ["LITELLM_API_KEY"]
ROOT = Path(__file__).resolve().parents[1]
RUN = uuid.uuid4().hex[:6]
failures = []


def call(method, path, body=None, key=KEY):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {key}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode() or "null"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as err:
        raw = err.read().decode()
        try:
            return err.code, json.loads(raw)
        except json.JSONDecodeError:
            return err.code, raw


def check(name, condition, detail=""):
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  -> {detail}"))
    if not condition:
        failures.append(name)


def expect(name, method, path, body=None, status=(200,), key=KEY):
    code, data = call(method, path, body, key)
    check(f"{name} [{method} {path.split('?')[0]} -> {code}]", code in status, str(data)[:300])
    return code, data


def mock_model(name, model):
    return {"model_name": name, "litellm_params": {"model": model, "api_key": "sk-mock", "mock_response": "ok"}}


# --- doctor / connect -------------------------------------------------------
_, details = expect("readiness details has version", "GET", "/health/readiness/details")
check("litellm_version present", isinstance(details, dict) and "litellm_version" in details, details)

# --- models -----------------------------------------------------------------
m = f"smoke-gpt-{RUN}"
code, created = expect("model new", "POST", "/model/new", mock_model(m, "openai/gpt-5.5"))
model_id = (created or {}).get("model_id") or (created or {}).get("model_info", {}).get("id")
check("model new returns model_id", bool(model_id), created)
expect("test_connection by model_info.id only", "POST", "/health/test_connection", {"model_info": {"id": model_id}})
expect("PATCH model update", "PATCH", f"/model/{model_id}/update", {"model_info": {"tier": "paid"}})
expect("model block", "POST", "/model/block", {"model_id": model_id})
expect("model unblock", "POST", "/model/unblock", {"model_id": model_id})
_, models = expect("v1/models", "GET", "/v1/models")
check("new model listed in /v1/models", m in [x["id"] for x in (models or {}).get("data", [])], "missing")

# --- teams ------------------------------------------------------------------
_, team = expect("team new (no alias required)", "POST", "/team/new", {"team_alias": f"smoke-team-{RUN}", "models": [m], "max_budget": 100})
team_id = team.get("team_id")
expect("team PATCH merge", "PATCH", f"/team/{team_id}", {"max_budget": 150})
_, info = expect("team info", "GET", f"/team/info?team_id={team_id}")
check("team PATCH kept models", info.get("team_info", {}).get("models") == [m], info.get("team_info", {}).get("models"))
check("team PATCH set budget", info.get("team_info", {}).get("max_budget") == 150, info.get("team_info", {}).get("max_budget"))
email = f"smoke-{RUN}@acme.test"
expect("team member_add by email", "POST", "/team/member_add", {"team_id": team_id, "member": {"user_email": email, "role": "user"}})
_, users = expect("user list by email", "GET", f"/user/list?user_email={email}")
member_id = ((users or {}).get("users") or [{}])[0].get("user_id")
expect("team member_update budget", "POST", "/team/member_update", {"team_id": team_id, "user_id": member_id, "max_budget_in_team": 100})
expect("team admin role is Enterprise-gated", "POST", "/team/member_update", {"team_id": team_id, "user_id": member_id, "role": "admin"}, status=(400, 401, 403))

# --- keys -------------------------------------------------------------------
alias = f"smoke-key-{RUN}"
_, key = expect("key generate", "POST", "/key/generate", {
    "key_alias": alias, "team_id": team_id, "models": [m], "max_budget": 50,
    "budget_duration": "30d", "rpm_limit": 60, "duration": "90d", "key_type": "llm_api"})
secret = key.get("key")
expect("duplicate alias rejected", "POST", "/key/generate", {"key_alias": alias}, status=(400,))
expect("key update merge by alias", "POST", "/key/update", {"key_alias": alias, "max_budget": 200})
_, kinfo = expect("key info", "GET", f"/key/info?key={secret}")
ki = kinfo.get("info", {})
check("merge kept models/rpm", ki.get("models") == [m] and ki.get("rpm_limit") == 60, ki)
check("merge set budget", ki.get("max_budget") == 200, ki.get("max_budget"))
code, _ = call("POST", "/chat/completions", {"model": m, "messages": [{"role": "user", "content": "hi"}]}, key=secret)
check("scoped key can call its model", code == 200, code)
expect("llm_api key blocked from admin route", "GET", "/key/list", key=secret, status=(401, 403))
expect("key list sorted by spend", "GET", "/key/list?return_full_object=true&size=5&sort_by=spend&sort_order=desc")
expect("key block", "POST", "/key/block", {"key": secret})
code, _ = call("POST", "/chat/completions", {"model": m, "messages": [{"role": "user", "content": "hi"}]}, key=secret)
check("blocked key is refused", code in (401, 403), code)
expect("key unblock", "POST", "/key/unblock", {"key": secret})
# v1.103 answers an unlicensed regenerate with 500; newer builds may use 4xx
expect("key regenerate works or is Enterprise-gated", "POST", f"/key/{secret}/regenerate", {"grace_period": "1h"}, status=(200, 400, 403, 500))
_, tiny = expect("tiny-budget key", "POST", "/key/generate", {"key_alias": f"smoke-tiny-{RUN}", "models": [m], "max_budget": 0.0000001})
call("POST", "/chat/completions", {"model": m, "messages": [{"role": "user", "content": "hi"}]}, key=tiny["key"])
time.sleep(12)  # spend is written in batches
code, err = call("POST", "/chat/completions", {"model": m, "messages": [{"role": "user", "content": "hi"}]}, key=tiny["key"])
err_type = (err.get("error") or {}).get("type") if isinstance(err, dict) else None
check("budget exceeded is 429/422 with type budget_exceeded", code in (422, 429) and err_type == "budget_exceeded", f"{code} {str(err)[:200]}")
expect("key delete by alias", "POST", "/key/delete", {"key_aliases": [alias, f"smoke-tiny-{RUN}"]})

# --- users ------------------------------------------------------------------
u_email = f"smoke-user-{RUN}@acme.test"
_, user = expect("user new", "POST", "/user/new", {"user_email": u_email, "user_role": "internal_user", "max_budget": 10})
expect("user new duplicate email is 409", "POST", "/user/new", {"user_email": u_email}, status=(409,))
# v1.103 accepts `password`; newer builds reject it with 422
_, pw_user = expect("user new with password (accepted on v1.103, 422 later)", "POST", "/user/new", {"user_email": f"pw-{RUN}@acme.test", "password": "x"}, status=(200, 422))
expect("user update", "POST", "/user/update", {"user_id": user.get("user_id"), "max_budget": 20})
expect("user delete", "POST", "/user/delete", {"user_ids": [u for u in (user.get("user_id"), member_id, (pw_user or {}).get("user_id")) if u]})

# --- orgs (expect Enterprise gate on an unlicensed proxy) --------------------
expect("orgs Enterprise gate or success", "POST", "/organization/new", {"organization_alias": f"smoke-org-{RUN}"}, status=(200, 403))

# --- MCP --------------------------------------------------------------------
expect("MCP hyphen name rejected", "POST", "/v1/mcp/server", {"server_name": "docs-search", "transport": "http", "url": "http://127.0.0.1:9/mcp"}, status=(400, 422))
srv_name = f"smoke_docs_{RUN}"
_, srv = expect("MCP create", "POST", "/v1/mcp/server", {
    "server_name": srv_name, "transport": "http", "url": "http://127.0.0.1:9/mcp",
    "auth_type": "bearer_token", "credentials": {"auth_value": "abc123"}}, status=(200, 201))
server_id = srv.get("server_id")
_, tl = expect("MCP pre-save test returns 200 with status in body", "POST", "/mcp-rest/test/connection", {"server_name": "probe", "transport": "http", "url": "http://127.0.0.1:9/mcp"})
check("test route reports error in body", isinstance(tl, dict) and tl.get("status") == "error", tl)
expect("MCP health", "GET", f"/v1/mcp/server/health?server_ids={server_id}")
expect("MCP partial PUT", "PUT", "/v1/mcp/server", {"server_id": server_id, "description": "smoke"}, status=(200, 202))
_, got = expect("MCP get", "GET", f"/v1/mcp/server/{server_id}")
check("partial PUT kept transport http", got.get("transport") == "http", got.get("transport"))
expect("MCP delete", "DELETE", f"/v1/mcp/server/{server_id}", status=(200, 202, 204))

# --- agents -----------------------------------------------------------------
_, agent = expect("agent create", "POST", "/v1/agents", {
    "agent_name": f"smoke_agent_{RUN}",
    "agent_card_params": {"name": "Smoke", "description": "smoke", "url": "http://127.0.0.1:9", "version": "1.0",
                          "protocolVersion": "1.0", "capabilities": {}, "defaultInputModes": ["text"],
                          "defaultOutputModes": ["text"], "skills": []},
    "rpm_limit": 30}, status=(200, 201))
agent_id = agent.get("agent_id")
_, full = expect("agent get", "GET", f"/v1/agents/{agent_id}")
card = dict(full.get("agent_card_params") or {})
card["description"] = "smoke v2"
expect("agent PATCH with full card", "PATCH", f"/v1/agents/{agent_id}", {"agent_card_params": card})
_, after = expect("agent get after patch", "GET", f"/v1/agents/{agent_id}")
check("agent PATCH kept url", (after.get("agent_card_params") or {}).get("url") == "http://127.0.0.1:9", after.get("agent_card_params"))
expect("agent delete", "DELETE", f"/v1/agents/{agent_id}")

# --- guardrails -------------------------------------------------------------
g_name = f"smoke_pii_{RUN}"
_, g = expect("guardrail create", "POST", "/guardrails", {"guardrail": {
    "guardrail_name": g_name,
    "litellm_params": {"guardrail": "litellm_content_filter", "mode": "pre_call",
                       "patterns": [{"pattern_type": "prebuilt", "pattern_name": "us_ssn", "action": "MASK"}]}}})
_, applied = expect("apply_guardrail", "POST", "/guardrails/apply_guardrail", {"guardrail_name": g_name, "text": "my ssn is 123-45-6789"}, status=(200, 400))
check("guardrail masked or blocked the SSN", "123-45-6789" not in json.dumps(applied), applied)
expect("guardrail delete", "DELETE", f"/guardrails/{g.get('guardrail_id')}")

# --- budgets and customers ---------------------------------------------------
b_id = f"smoke-tier-{RUN}"
expect("budget new", "POST", "/budget/new", {"budget_id": b_id, "max_budget": 50, "budget_duration": "30d"})
c_id = f"smoke-cust-{RUN}"
expect("customer new on tier", "POST", "/customer/new", {"user_id": c_id, "budget_id": b_id})
expect("customer block via update", "POST", "/customer/update", {"user_id": c_id, "blocked": True})
expect("customer unblock via update", "POST", "/customer/update", {"user_id": c_id, "blocked": False})
cap_id = f"smoke-cap-{RUN}"
expect("customer with tiny budget", "POST", "/customer/new", {"user_id": cap_id, "max_budget": 0.0000001})
_, ck = expect("key for customer calls", "POST", "/key/generate", {"key_alias": f"smoke-cust-key-{RUN}", "models": [m]})
call("POST", "/chat/completions", {"model": m, "user": cap_id, "messages": [{"role": "user", "content": "hi"}]}, key=ck["key"])
time.sleep(12)
code, err = call("POST", "/chat/completions", {"model": m, "user": cap_id, "messages": [{"role": "user", "content": "hi"}]}, key=ck["key"])
check("customer budget is enforced", code in (400, 422, 429) and "budget" in json.dumps(err).lower(), f"{code} {str(err)[:200]}")
call("POST", "/key/delete", {"key_aliases": [f"smoke-cust-key-{RUN}"]})
call("POST", "/customer/delete", {"user_ids": [cap_id]})
expect("customer delete", "POST", "/customer/delete", {"user_ids": [c_id]})
expect("budget delete", "POST", "/budget/delete", {"id": b_id})

# --- usage ------------------------------------------------------------------
today = time.strftime("%Y-%m-%d")
expect("daily activity needs dates", "GET", "/user/daily/activity", status=(400, 422))
_, agg = expect("user aggregated", "GET", f"/user/daily/activity/aggregated?start_date={today}&end_date={today}")
check("aggregated has metadata.total_spend", "total_spend" in (agg or {}).get("metadata", {}), (agg or {}).get("metadata"))
expect("team aggregated", "GET", f"/team/daily/activity/aggregated?team_ids={team_id}&start_date={today}&end_date={today}")
expect("spend logs v2", "GET", f"/spend/logs/v2?start_date={today}%2000:00:00&end_date={today}%2023:59:59&page_size=5")

# --- bundled scripts ---------------------------------------------------------
env = dict(os.environ)
for script, args in [
    ("litellm-usage/scripts/usage_report.py", ["--by", "team", "--ids", team_id, "--start", today, "--end", today, "--json"]),
    ("litellm-budgets/scripts/budget_check.py", ["--json"]),
    ("litellm-doctor/scripts/doctor.py", []),
]:
    proc = subprocess.run([sys.executable, str(ROOT / script), *args], capture_output=True, text=True, env=env, timeout=180)
    check(f"script {script} exits 0", proc.returncode == 0, (proc.stderr or proc.stdout)[-400:])

# --- cleanup ----------------------------------------------------------------
call("POST", "/team/delete", {"team_ids": [team_id]})
call("POST", "/model/delete", {"id": model_id})

print(f"\n{len(failures)} failed")
sys.exit(len(failures))
