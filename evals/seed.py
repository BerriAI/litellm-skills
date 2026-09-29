"""Seed a DISPOSABLE LiteLLM proxy with the state evals/evals.json expects.

    LITELLM_BASE_URL=http://localhost:4100 LITELLM_API_KEY=<master key> python3 evals/seed.py > ground_truth.json

Models use `mock_response`, so no provider keys are needed. Prints ground truth
(team spend, seeded key settings) as JSON on stdout.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ["LITELLM_BASE_URL"].rstrip("/")
KEY = os.environ["LITELLM_API_KEY"]


def call(method, path, body=None, key=KEY):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {key}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode() or "null")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()


def must(method, path, body=None, key=KEY):
    code, data = call(method, path, body, key)
    if code >= 300:
        sys.exit(f"seed failed: {method} {path} -> {code} {data}")
    return data


for name, model in [
    ("gpt-5.5", "openai/gpt-5.5"),
    ("claude-sonnet-5-5", "anthropic/claude-sonnet-5-5"),
    ("gpt-5.4-mini", "openai/gpt-5.4-mini"),
]:
    must("POST", "/model/new", {"model_name": name, "litellm_params": {"model": model, "api_key": "sk-mock", "mock_response": "Hello from the mock model."}})

teams = {}
for alias in ["data-science", "marketing", "platform"]:
    teams[alias] = must("POST", "/team/new", {"team_alias": alias, "models": ["gpt-5.5", "claude-sonnet-5-5", "gpt-5.4-mini"]})["team_id"]

seeded_keys = {
    "marketing-bot": {"team_id": teams["marketing"], "models": ["gpt-5.5"], "rpm_limit": 30, "max_budget": 20, "duration": "60d", "metadata": {"owner": "marketing"}},
    "support-bot": {"models": ["gpt-5.5"], "max_budget": 0.0001},
    "ci-runner": {"team_id": teams["platform"], "models": ["gpt-5.4-mini"], "rpm_limit": 120},
}
secrets = {}
for alias, body in seeded_keys.items():
    secrets[alias] = must("POST", "/key/generate", {"key_alias": alias, **body})["key"]

# Traffic: per-team volumes differ so the ranking is unambiguous.
traffic = {"data-science": (40, "claude-sonnet-5-5"), "marketing": (20, "gpt-5.5"), "platform": (8, "gpt-5.4-mini")}
for alias, (n, model) in traffic.items():
    k = must("POST", "/key/generate", {"key_alias": f"{alias}-traffic", "team_id": teams[alias], "models": [model]})["key"]
    for i in range(n):
        call("POST", "/chat/completions", {"model": model, "messages": [{"role": "user", "content": f"request {i} " + "tokens " * (10 * (i % 5 + 1))}]}, key=k)

# Push support-bot over its budget.
for _ in range(3):
    call("POST", "/chat/completions", {"model": "gpt-5.5", "messages": [{"role": "user", "content": "hi " * 200}]}, key=secrets["support-bot"])
    time.sleep(6)

time.sleep(20)  # let batched spend writes land in the daily tables
today = time.strftime("%Y-%m-%d")
month_start = time.strftime("%Y-%m-01")
agg = must("GET", f"/team/daily/activity/aggregated?team_ids={','.join(teams.values())}&start_date={month_start}&end_date={today}")
team_spend = {}
for row in agg.get("results", []):
    for team_id, entity in (row.get("breakdown", {}).get("entities") or {}).items():
        team_spend[team_id] = team_spend.get(team_id, 0) + entity.get("metrics", {}).get("spend", 0)
by_alias = {alias: round(team_spend.get(tid, 0), 8) for alias, tid in teams.items()}

print(json.dumps({
    "teams": teams,
    "team_spend": by_alias,
    "total_team_spend": round(sum(by_alias.values()), 8),
    "seeded_keys": {k: {kk: vv for kk, vv in v.items() if kk != "team_id"} for k, v in seeded_keys.items()},
}, indent=2))
