---
name: litellm-budgets
description: >
  Manage spend limits on a live LiteLLM proxy (AI gateway) with curl: reusable
  budget tiers (/budget/*), customers or end users and their budgets
  (/customer/*), shared budgets on model access groups, provider budgets, and a
  check of who is near or over budget. Use this whenever someone wants to
  create a "free tier" or "pro tier" budget, cap what an external customer
  (the `user` field on requests) can spend, block or unblock a customer, give a
  group of models one shared monthly cap, see which keys, users, teams, orgs,
  or customers are about to hit their limit, or understand why requests are
  failing with budget_exceeded. Also use it for "set a $50/month limit per
  customer", "who is over budget", "budget alerts", and "end user spend", even
  when the user never says "budget endpoint". Budgets set directly on a key,
  user, team, or org live in those skills; this one covers shared and
  customer-facing budgets.
license: MIT
compatibility: Requires curl and python3. Written against LiteLLM v1.103 (September 2026).
metadata:
  author: BerriAI
  version: "2.0"
allowed-tools: Bash(curl:*) Bash(python3:*)
---

# LiteLLM budgets

A budget is a row with `max_budget`, `soft_budget`, `budget_duration`, and
rate limits. Keys, orgs, customers, tags, team memberships and access groups
point at one through `budget_id`. For keys, orgs, customers and tags the row
is a tier: every attached object gets its own spend counter checked against
the same limit. An access group budget is a single pool shared by every key
that can reach the group.

## Connect

Read `LITELLM_BASE_URL` and `LITELLM_API_KEY` from the environment. If either is
missing, ask for it once and export it for the rest of the session. The key must
be a proxy admin key; `proxy_admin_viewer` can read budgets and customers but
not change them. Never echo the admin key or a newly generated key back into
logs you don't need to.

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
| Who is near or over budget | `python3 scripts/budget_check.py` |
| Create a reusable tier | `POST /budget/new` |
| See budgets | `GET /budget/list`, `GET /management/v1/budgets` (v1.96+), `POST /budget/info` |
| Change a tier (affects everything attached) | `POST /budget/update` |
| Delete a tier | `POST /budget/delete` |
| Create, see, update, delete a customer | `/customer/new`, `/customer/info`, `/customer/list`, `/customer/update`, `/customer/delete` |
| Block or unblock a customer (Enterprise enforcement) | `POST /customer/update {"blocked": true\|false}` |
| One shared cap for a model access group | `GET/PUT/DELETE /access_group/{group}/budget` (v1.100+) |
| Provider-wide caps (e.g. $100/day on openai) | config `router_settings.provider_budget_config`; read with `GET /provider/budgets` |
| Customer spend over time | litellm-usage skill, `/customer/daily/activity` |

`/end_user/*` paths are hidden aliases of `/customer/*`.

## How limits behave

- Past `max_budget`, requests fail with error type `budget_exceeded`. v1.103 and
  earlier return HTTP 429; builds after v1.103 return 422 by default
  (`litellm_settings.budget_exceeded_status_code` picks the code). Match on the
  type, not the status. `soft_budget` only alerts.
- `budget_duration` (`30s`, `30m`, `12h`, `1d`, `7d`, `1w`, `1mo`) resets the
  counter; `budget_reset_at` is the next reset. Without a duration the budget
  never resets. `budget_reset_time: "09:00"` in `litellm_settings` moves day,
  week and month resets off midnight (v1.95+).
- `budget_rollover: true` in `litellm_settings` carries over-cap spend into the
  next window instead of forgiving it (v1.100+, default off).
- `max_budget: 0` means no allowance; `null` means unlimited. Orgs and projects
  treated 0 as unlimited before v1.103.
- Team keys obey team and team-member budgets, not the user's personal budget,
  unless `general_settings.apply_user_budget_to_team_keys: true` (v1.97+).
- A key can keep serving at reduced TPM/RPM instead of hard-failing when it has
  `throttle_on_budget_exceeded: true` and the proxy sets
  `litellm_settings.budget_exceeded_throttle_percentage`. Off by default.

More fields and version notes: `references/fields.md`.

## Who is near or over budget

The script lives in this skill's directory; run it from there or give its full
path.

```bash
python3 scripts/budget_check.py                      # everything at >= 80% of its cap
python3 scripts/budget_check.py --threshold 0.5 --only keys,teams,customers --json
```

It pages `/key/list`, `/user/list`, `/v2/team/list`, and reads
`/organization/list`, `/customer/list`, `/access_group/list`, then prints
`over` (spend at or past `max_budget`, being rejected now), `near`, and `soft`
(past `soft_budget` only) rows with spend, cap, percent and next reset. The
`spend` it compares is the resettable counter enforcement uses, so it answers
"will this be blocked", not "what did this cost this month". Customers with no
budget of their own fall under the proxy default (`max_end_user_budget_id`),
which the script cannot see; mention that when customers show no cap.

## Reusable budgets

```bash
curl -sS -X POST "$LITELLM_BASE_URL/budget/new" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"budget_id": "pro-tier", "max_budget": 50, "soft_budget": 40, "budget_duration": "1mo", "rpm_limit": 120}'
```

Fields: `budget_id` (generated if omitted; a duplicate gives 400),
`max_budget`, `soft_budget`, `budget_duration`, `tpm_limit`, `rpm_limit`,
`tpd_limit`, `max_parallel_requests`, `model_max_budget`
(`{"gpt-5.5": {"max_budget": 20, "budget_duration": "1mo"}}`), `budget_reset_at`.
Attach it with `budget_id` on `/key/generate`, `/customer/new`,
`/organization/new`, `/tag/new`, or the access group PUT below.

```bash
curl -sS "$LITELLM_BASE_URL/budget/list" -H "Authorization: Bearer $LITELLM_API_KEY"   # bare array
curl -sS -g "$LITELLM_BASE_URL/management/v1/budgets?sort=-max_budget&filter[budget_duration][in]=1mo,30d&page_size=25" \
  -H "Authorization: Bearer $LITELLM_API_KEY"   # {data, meta: {total_count, page, page_size, total_pages}, links}
curl -sS -X POST "$LITELLM_BASE_URL/budget/info" -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" -d '{"budgets": ["pro-tier"]}'
```

`/budget/update` needs `budget_id` and merges: omitted fields keep their
value, an explicit `null` clears one. Changing `budget_duration` recomputes the
next reset. Because every attached key, customer or org reads this row, say how
many objects use it before changing a shared tier.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/budget/update" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' -d '{"budget_id": "pro-tier", "max_budget": 75}'
```

Delete (proxy admin only) takes `{"id": "<budget_id>"}`. Check first what points
at it (`/customer/list`, `/key/list?return_full_object=true`, orgs, access
groups), show the user, and get an explicit yes. Deletion is permanent and
nothing reassigns the objects that used it, so move them to another
`budget_id` first; a delete that still has an org attached can fail with a
database error.

## Customers (end users)

A customer is whatever id the caller sends as `user` in the request body (also
`x-litellm-customer-id` / `x-litellm-end-user-id` headers, `metadata.user_id`,
or `safety_identifier`). The first request with a new id creates the customer
row automatically, so a customer that already sent traffic must be changed
with `/customer/update`; `/customer/new` on it returns 400 "Customer already
exists".

```bash
curl -sS -X POST "$LITELLM_BASE_URL/customer/new" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"user_id": "acme-corp", "alias": "Acme Corp", "budget_id": "pro-tier"}'
# or a private budget: "max_budget": 25, "budget_duration": "1mo" (not together with budget_id)
```

Other fields: `allowed_model_region` (`eu`/`us`), `default_model` (must exist
on the proxy), `blocked`, `spend`, `object_permission` (MCP servers, agents,
vector stores). Read with `GET /customer/info?end_user_id=acme-corp`; list all
with `GET /customer/list` (admin only, one unpaginated array).

`/customer/update` takes `user_id` plus `alias`, `blocked`, `max_budget`,
`budget_id`, `allowed_model_region`, `default_model`, `object_permission`.
Sending `max_budget` edits the budget row the customer points at; if that is a
shared tier, every customer on the tier changes. To change one customer, point
it at another tier with `budget_id` instead. `max_budget: 0` is ignored here,
and `budget_duration` is not accepted; change it on the budget with
`/budget/update`.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/customer/update" -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" -d '{"user_id": "acme-corp", "blocked": true}'
# unblock: same call with "blocked": false
```

The `blocked` flag is only enforced when the proxy runs the Enterprise
`blocked_user_check` callback (`litellm_settings.callbacks: ["blocked_user_check"]`
plus a license). Without it the flag is stored but the customer's requests keep
succeeding, so check the proxy config (`GET /active/callbacks`) and tell the user
before promising a block; the alternative is `max_budget` near zero on the
customer's budget. Prefer `/customer/update` for both directions:
`/customer/block` writes the flag but returns HTTP 500 on v1.103 (a response
serialization bug), and `/customer/unblock` only edits the enterprise
`blocked_user_list` and returns 400 when that list is not configured.

`POST /customer/delete {"user_ids": [...]}` removes the rows (404 if any id is
missing). Look them up first and confirm; spend history stays in the daily
tables, and the next request with that id recreates an unbudgeted customer, so
block instead when the goal is to stop traffic.

## Access group budgets (v1.100+)

```bash
curl -sS -X PUT "$LITELLM_BASE_URL/access_group/production-models/budget" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' -d '{"max_budget": 500, "budget_duration": "1mo"}'
```

Body: any of `max_budget`, `soft_budget`, `budget_duration`, `budget_id`; other
fields (rate limits) are rejected with 422. Response: `access_group`, shared
`spend`, and `budget`. `GET` reads it, `DELETE` clears it and leaves the group.

## Errors

- **400 "Budget with id ... already exists"**: pick another `budget_id` or update.
- **400 invalid `budget_duration`** / negative `max_budget`: use `1d`, `30d`, `1mo`.
- **400 "Not allowed access"** on `/budget/list` or `/budget/delete`: not an admin key.
- **401 "Admin-only endpoint"**: `/customer/list` or customer activity without an admin role.
- **400 "Customer already exists"**: the id already sent traffic; use `/customer/update`.
- **404 "End User Id=... does not exist"**: create the customer first.
- **422 "Set either 'max_budget' or 'budget_id', not both"**, or `default_model` not on the proxy.
- **422 / 429 `budget_exceeded`** on inference: the message names the blocking entity; raise its budget, add `temp_budget_increase` on a key, or wait for `budget_reset_at`.
- Anything else: show `detail` / `error.message` verbatim.

Docs: https://docs.litellm.ai/docs/proxy/customers, https://docs.litellm.ai/docs/proxy/model_access_group_budgets
