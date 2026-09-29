---
name: litellm-keys
description: >
  Create, inspect, update, rotate, block, and delete virtual API keys on a live
  LiteLLM proxy (AI gateway) with curl. Use this whenever someone wants to give a
  person, app, agent, or team an API key for LiteLLM; set or change a key's
  budget, rate limits, allowed models, or expiry; rotate or regenerate a key;
  temporarily disable (block) or re-enable a key; find a key by alias; or revoke
  keys. Also use it when a user says "sk-..." key, "virtual key", or wants to
  raise, reset, or temporarily increase one key's budget.
license: MIT
compatibility: Requires curl and python3. Written against LiteLLM v1.103 (September 2026).
metadata:
  author: BerriAI
  version: "2.0"
allowed-tools: Bash(curl:*) Bash(python3:*)
---

# LiteLLM keys

Virtual keys are how LiteLLM hands out access. Every key can carry its own
budget, rate limits, model allowlist, expiry, and owner (user, team, org).

## Connect

Read `LITELLM_BASE_URL` and `LITELLM_API_KEY` from the environment. If either is
missing, ask for it once and export it for the rest of the session. The key must
be a proxy admin key (or a team admin key for keys inside that team). Never echo
the admin key or a newly generated key back into logs you don't need to.

```bash
curl -sS "$LITELLM_BASE_URL/health/readiness/details" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

Skip it if you already checked this proxy earlier in the session. It confirms
the URL and key work and returns `litellm_version`. Features
below that changed recently name the version they arrived in; if the proxy is
older, say so instead of guessing.

Append `-w '\nHTTP %{http_code}\n'` to write calls so the status is visible.

## Pick the operation

| The user wants to | Call |
|---|---|
| Create a key | `POST /key/generate` |
| See one key | `GET /key/info?key=<key or hash>` |
| Find keys | `GET /key/list` |
| Change budget, limits, models, expiry, owner | `POST /key/update` |
| Rotate (new secret, same settings) | `POST /key/{key}/regenerate` (Enterprise) |
| Temporarily disable or re-enable | `POST /key/block`, `POST /key/unblock` |
| Reset spend to zero | `POST /key/{key}/reset_spend` |
| Revoke permanently | `POST /key/delete` |

Keys are identified by the raw `sk-...` value, its sha256 hash (the `token`
field that `/key/list` returns), or on `/key/update` and `/key/delete` by
`key_alias`. Prefer the hash or alias in URLs so the raw key stays out of access
logs.

## Create a key

Ask only for what matters to the request; everything is optional.

1. `key_alias`, recommended and must be unique (e.g. `billing-agent-prod`)
2. Owner: `user_id`, `team_id`, and/or `organization_id`
3. `models`, the public model names this key may call (empty means whatever the
   owner is allowed)
4. `max_budget` in USD and `budget_duration` (`30d`, `1mo`, `7d`) if it should reset
5. `tpm_limit`, `rpm_limit`, and `tpd_limit` (tokens per day, v1.103+)
6. `duration` until expiry (`30d`, `90d`); omit for a key that never expires

```bash
curl -sS -X POST "$LITELLM_BASE_URL/key/generate" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{
    "key_alias": "billing-agent-prod",
    "team_id": "<team_id>",
    "models": ["gpt-5.5", "claude-sonnet-5-5"],
    "max_budget": 50,
    "budget_duration": "30d",
    "rpm_limit": 60,
    "duration": "90d"
  }'
```

Only send fields the user asked for. Show the user `key` (the only time the raw
secret is returned; tell them to store it now), `key_alias`, `expires`,
`max_budget`, `models`, and `budget_reset_at` when a `budget_duration` is set.
Resets land on standardized boundaries (a `30d` or `1mo` budget created
mid-month first resets at the start of next month), so the first window is
often shorter than the duration; say so.

For per-model budgets, per-model rate limits, multiple budget windows,
guardrails, tags, MCP or agent access, auto-rotation, and machine-only keys,
read `references/fields.md`.

## Inspect and find keys

```bash
# one key
curl -sS "$LITELLM_BASE_URL/key/info?key=<sk-... or sha256 hash>" \
  -H "Authorization: Bearer $LITELLM_API_KEY"

# list, newest first; filters: team_id, user_id, organization_id, key_alias,
# status=active|expired|revoked, sort_by=spend, substring_matching=true
curl -sS "$LITELLM_BASE_URL/key/list?return_full_object=true&size=50&sort_by=spend&sort_order=desc" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

`/key/list` returns `keys`, `total_count`, `current_page`, `total_pages`; `size`
caps at 100, so page with `page=` when `total_pages > 1`. Each key's `token` is
the hash, not the secret.

## Update a key

`/key/update` is a merge patch: fields you leave out keep their stored value,
and an explicit `null` clears a column. So send only what changes, and never
send placeholder nulls.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/key/update" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"key_alias": "billing-agent-prod", "max_budget": 100}'
```

Useful update-only fields: `duration` (restarts expiry from now; `null` means
never expire), `blocked`, `soft_budget` (alert threshold), and
`temp_budget_increase` together with `temp_budget_expiry` (ISO timestamp) for a
temporary bump. Moving a key to a different `project_id` is rejected.

## Rotate a key (Enterprise)

```bash
curl -sS -X POST "$LITELLM_BASE_URL/key/<sk-... or hash>/regenerate" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"grace_period": "24h"}'
```

The response carries the new `key`. Without `grace_period` the old secret stops
working immediately, which breaks anything still using it; suggest a grace
period unless the key leaked. The same body accepts any create field to change
settings during rotation. For scheduled rotation set `auto_rotate: true` and
`rotation_interval: "30d"` on create or update instead. An unlicensed proxy
answers with HTTP 500 "Regenerating Virtual Keys is an Enterprise feature".

## Block, unblock, reset spend

```bash
curl -sS -X POST "$LITELLM_BASE_URL/key/block" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key": "<sk-... or hash>"}'
# /key/unblock takes the same body

curl -sS -X POST "$LITELLM_BASE_URL/key/<sk-... or hash>/reset_spend" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"reset_to": 0}'
```

Blocking is the right answer for "turn this off for now" or an incident: it is
reversible and keeps history. Suggest it before deleting.

## Delete keys

Look the key(s) up first, show alias, owner, and spend, and get an explicit yes.
Deletion is permanent and every client using the key starts getting 401s.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/key/delete" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"key_aliases": ["billing-agent-prod"]}'
# or {"keys": ["<sk-... or hash>"]}
```

The response lists `deleted_keys`.

## Errors

- **401**: the admin key is wrong or is itself a scoped virtual key.
- **403**: not allowed. Setting `permissions` or `allowed_routes` needs a proxy
  admin (v1.92+); team admins can only manage keys in their team.
- **400 duplicate alias** or **invalid alias**: aliases must be unique and may
  not contain path traversal or control characters.
- **400 "Only premium users..." / "only available for LiteLLM Enterprise"**:
  `tags`, `guardrails`, `policies`, `prompts`, and `disable_global_guardrails`
  need an Enterprise license. Drop the field or tell the user.
- **500 "Regenerating Virtual Keys is an Enterprise feature"** on
  `/key/{key}/regenerate`: no license. This is a licensing refusal, not a crash;
  tell the user rotation needs Enterprise, or create a new key and delete the old.
- **Clients of the key get `"type": "budget_exceeded"`** (HTTP 429 on v1.103,
  422 on builds after v1.103): compare `spend` with
  `max_budget` in `/key/info`, then raise the budget, add a temporary increase,
  or reset spend. A **429** without that type is a rate limit (`rpm_limit`,
  `tpm_limit`, `max_parallel_requests`), not budget.
- Anything else: show `detail` / `error.message` verbatim and the likely fix.
