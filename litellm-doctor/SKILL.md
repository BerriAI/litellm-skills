---
name: litellm-doctor
description: >
  Diagnose a live LiteLLM proxy (AI gateway) with read-only curl checks and a
  bundled report script. Reach for this first whenever someone says the proxy
  or gateway is failing, down, slow, or "not working"; requests return 401,
  403, 404, 422, 429, 500, or 503; asks "is my proxy up", "which version am I
  on", "what's configured", "do I have an Enterprise license"; asks why a key
  can't call a model or why a key suddenly stopped working; sees "Budget has
  been exceeded", "Invalid model name passed in", "No deployments available",
  or "Rate limit exceeded"; or wants to know why a model isn't showing up. It finds
  the cause and points to the fix, and changes nothing unless asked.
license: MIT
compatibility: Requires curl and python3. Written against LiteLLM v1.103 (September 2026).
metadata:
  author: BerriAI
  version: "2.0"
allowed-tools: Bash(curl:*) Bash(python3:*)
---

# LiteLLM doctor

Everything here is a GET unless noted, so it is safe to run on production.
Work from the outside in: is the process up, is the database up, does the key
authenticate, can the key reach the model, is the provider answering. Stop at
the first layer that fails and fix that. Hand the fix itself to the owning
skill (`litellm-keys`, `litellm-models`, `litellm-budgets`, ...) and ask before
any write.

## Connect

Read `LITELLM_BASE_URL` and `LITELLM_API_KEY` from the environment. If either is
missing, ask for it once and export it for the rest of the session. The key
should be a proxy admin key (a `proxy_admin_viewer` key can read almost all of
this since v1.97); with only a user's virtual key you can still run the
liveness, readiness, `/v1/models`, and `/key/info` checks for that key. Never
echo the admin key or a newly generated key back into logs you don't need to.

```bash
curl -sS "$LITELLM_BASE_URL/health/readiness/details" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

Skip it if you already checked this proxy earlier in the session. It confirms
the URL and key work and returns `litellm_version`. Features
below that changed recently name the version they arrived in; if the proxy is
older, say so instead of guessing.

Append `-w '\nHTTP %{http_code}\n'` to write calls so the status is visible.

## Start narrow when the user names a key or model

For "key X is failing" or "key X can't call model Y", go straight to
`GET /key/info` and that key's recent failures in `/spend/logs/v2`
(`status_filter=failure`, `key_alias=` or `api_key=`); the sections below show
both. Run the full report only when that does not explain it or the problem is
proxy-wide.

## Run the report

The script lives in this skill's directory; run it from there or give its full
path.

```bash
python3 scripts/doctor.py                                    # whole proxy
python3 scripts/doctor.py --key <sk-... or hash> --model gpt-5.5   # why can't this key call X?
python3 scripts/doctor.py --hours 6 --json                   # machine-readable
python3 scripts/doctor.py --probe-model claude-sonnet-5-5    # also live-probe one model
```

It runs liveness, readiness, version, environment, license, visible models,
deprecations, callbacks, and groups the last 24h of failed requests by status,
error class, and model with a likely cause for each group. It only sends GETs;
`--probe-model` makes one real LLM call per deployment of that model, so it is
opt-in. Exit code is 1 when any check fails. Read its output, then use the
sections below to dig into whatever it flagged.

## Pick the check

| The user asks | Call |
|---|---|
| Is it up? | `GET /health/liveliness` (no auth), `GET /health/readiness` (no auth) |
| Which version / what's configured? | `GET /health/readiness/details`, `GET /config/list?config_type=general_settings`; optionally `GET /debug/report` (builds after v1.103) |
| Enterprise or not? | `GET /health/license` |
| Why can't key X call model Y? | `GET /key/info?key=...`, then `GET /v1/models` with that key |
| Is model Y working? | `GET /health?model=Y` (costs one call per deployment) |
| What is failing and why? | `GET /spend/logs/v2?status_filter=failure&...` |
| What callbacks/logging are on? | `GET /active/callbacks` |
| Is the proxy saturated? | `GET /health/backlog` |

## Up, ready, version

`/health/liveliness` returns `"I'm alive!"` while the worker runs (503 once it
starts shutting down). `/health/readiness` returns only `status` and `db`
(since v1.84); on v1.103 `db` is `connected`, `disconnected`, or `Not
connected` (no database configured), and builds after v1.103 add `stalled`
(Postgres answering too slowly). A configured but unreachable database makes
it 503. `/health/readiness/details` (authenticated) adds
`litellm_version`, `cache`, `success_callbacks`, `log_level`,
`is_detailed_debug`, and `show_no_redis_warning` (several workers without Redis
means rate limits and caches are per-process).

```bash
curl -sS "$LITELLM_BASE_URL/debug/report" -H "Authorization: Bearer $LITELLM_API_KEY"
```

Optional, builds after v1.103 only: v1.103 and earlier return 404, so rely on
`/health/readiness/details` there. Proxy admin only. Returns `litellm_version`,
`python_version`, `deployment` (`Docker` or null), and `config_lines`, the
config flags LiteLLM itself defines, with no secrets. `GET /health/license`
returns `license_type` (`enterprise` or `community`) and `expiration_date`. `GET /config/list
?config_type=general_settings` shows each general setting with `source` and
`editable` (v1.103+); since v1.103 a setting declared in config.yaml rejects
runtime writes with 400, so "my settings change didn't stick" usually means the
file owns it.

## Why can't this key call this model?

```bash
curl -sS "$LITELLM_BASE_URL/key/info?key=<sk-... or hash>" -H "Authorization: Bearer $LITELLM_API_KEY"
curl -sS "$LITELLM_BASE_URL/v1/models" -H "Authorization: Bearer <the user's sk-... key>"
```

In `info`, check in order: `blocked`; `expires` in the past; `spend` at or
above `max_budget` (and `budget_reset_at`); `models` (empty means it inherits
the team's or user's list; names can be access groups); `key_type` (`llm_api`
keys cannot call admin routes); `rpm_limit` / `tpm_limit`; then `team_id`,
because the team's models, budget, and limits apply on top (`/team/info`).
`/v1/models` with the user's own key is the ground truth for what that key can
call; if the model is missing there but exists in `/model/info`, it is access,
not configuration. Clients may send the key as `x-litellm-api-key: sk-...`
instead of `Authorization: Bearer`; both work.

## Is the model healthy?

```bash
curl -sS "$LITELLM_BASE_URL/health?model=gpt-5.5" -H "Authorization: Bearer $LITELLM_API_KEY"
curl -sS "$LITELLM_BASE_URL/model/info?litellm_model_id=<model_id>" -H "Authorization: Bearer $LITELLM_API_KEY"
```

`/health` makes a real, tiny request to every matching deployment and returns
`healthy_endpoints`, `unhealthy_endpoints` (each with `error`), and counts;
without `?model=` or `?model_id=` it probes every model, which is slow and
costs money on large proxies, so target one. A targeted check where nothing is
healthy returns 503. Since v1.102 non-admin keys only see deployments they may
use, and `api_base` is admin-only. The `x-litellm-model-id` response header on
a real call gives the `model_id` that served it. `GET /model/deprecations`
lists models past or near their provider deprecation date.

## What is failing?

```bash
curl -sS "$LITELLM_BASE_URL/spend/logs/v2?start_date=2026-09-29%2000:00:00&end_date=2026-09-29%2023:59:59&status_filter=failure&page_size=50" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

Add `error_code=429`, `model_group=`, `key_alias=`, or `error_message=` (partial
match) to narrow it. Each row's `metadata.error_information` has `error_code`,
`error_class`, `error_message`, `llm_provider`, and for 429s
`error_rate_limit_category` (`litellm_rate_limit` is the proxy's own limiter,
`vendor_rate_limit` is the provider) and `error_rate_limit_type` (`requests`,
`tokens`, `concurrent_requests`, `budget`). Requests by the master key show
`api_key` as `litellm_proxy_master_key` (v1.84+).
`GET /gateway/daily/activity` (proxy admin, newest builds) counts
successes and failures per route at the HTTP edge, including requests that
never reached logging.

## Symptom, check, fix

Read `references/symptoms.md` for the full table with exact error strings.
The short version:

| Symptom | Most likely | Confirm | Fix |
|---|---|---|---|
| 401 on every call | Wrong, deleted, expired, or blocked key | `/key/info`; message says "Expired Key" or "Key is blocked" | New key, `/key/update duration`, `/key/unblock` |
| 401 "Only proxy admin can be used..." | Valid key, admin route | key's user role | Use an admin key |
| 403 "not available for this API key" | Model not in key/team/user `models` | `/key/info`, `/v1/models` with that key | Add the model or access group |
| 403 "not allowed to call this route" | `key_type`/`allowed_routes` | `info.key_type` | Use a `default` or admin key |
| 403 "Enterprise"/"premium" | Licensed feature | `/health/license` | License, or drop the field |
| 400 "Invalid model name passed in" | Name not on proxy | `/v1/models`, `/model/info` | Fix name, add model or alias |
| 429 (v1.103) or 422 (newer) "Budget has been exceeded!" | Key, team, user, or member budget | `error.type` is `budget_exceeded`; message names which | Raise budget or wait for reset |
| 429 "Rate limit exceeded for ..." | Proxy rpm/tpm/parallel limit | message names key/team/user and limit | Raise the limit |
| 429 from provider | Upstream quota | `error_rate_limit_category: vendor_rate_limit` | More deployments, fallbacks |
| 500 naming a provider | Provider error or bad credentials | `/health?model=...` | Fix credentials/`api_base` |
| 503 `no_db_connection` / readiness `db: disconnected` | Postgres down | `/health/readiness` | Restore DB |
| Model added but not callable | Other replicas not synced yet | `/model/info` on each pod | Wait 30s (`PROXY_CONFIG_RELOAD_INTERVAL_SECONDS`) |
| Slow responses | Provider latency vs proxy overhead | `x-litellm-overhead-duration-ms`, `/health/backlog` | See `references/symptoms.md` |

## Errors

- **401 on the doctor calls themselves**: the admin key is wrong; say so and
  ask for the right one rather than guessing.
- **403 on `/debug/report`** (builds after v1.103): proxy admin only ("Only
  proxy admins can read /debug/report"); a viewer key is not enough.
- **403 on `/gateway/daily/activity`**: needs a proxy admin or admin viewer key.
- **404 on a check**: the endpoint is newer than the proxy; note the version
  and skip it.
- **400/500 "DB not connected" on `/spend/logs/v2`, `/key/info`**: the
  proxy runs without `DATABASE_URL`, so there are no virtual keys or logs;
  diagnose from `/health` and the proxy's stdout instead.
- Docs: https://docs.litellm.ai/docs/proxy/health and
  https://docs.litellm.ai/docs/troubleshoot
