---
name: litellm-orgs
description: >
  Create, inspect, update, and delete organizations on a live LiteLLM proxy (AI
  gateway) with curl, and manage who belongs to them, including granting or
  revoking org_admin. Organizations sit above teams: they own teams, cap their
  budgets and models, and let an org admin run their own slice of the gateway.
  Use this whenever someone wants a separate internal business unit, tenant,
  department, or subsidiary that owns its own teams, budget, and model access; wants to make
  someone an org admin; asks to move a team under an org, list orgs, change an
  org's budget or allowed models, add or remove org members, or tear down an
  org. Organizations need a LiteLLM Enterprise license (v1.102+).
license: MIT
compatibility: Requires curl and python3. Written against LiteLLM v1.103 (September 2026).
metadata:
  author: BerriAI
  version: "2.0"
allowed-tools: Bash(curl:*) Bash(python3:*)
---

# LiteLLM organizations

Hierarchy: organization > teams > users and keys. An org has one budget row
(`max_budget`, limits, `budget_duration`) and a model allowlist that cap
everything inside it, plus members with an org role: `org_admin` (can create
teams and users inside the org), `internal_user`, or `internal_user_viewer`.

**Check the license first.** Since v1.102 every organization endpoint returns
403 without an Enterprise license, so confirm before building anything:

```bash
curl -sS "$LITELLM_BASE_URL/health/license" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

If `license_type` is `community`, stop and tell the user orgs need
LiteLLM Enterprise; suggest teams (`litellm-teams`) for grouping and budgets
instead. On proxies older than v1.102 org endpoints work without a license.

## Connect

Read `LITELLM_BASE_URL` and `LITELLM_API_KEY` from the environment. If either is
missing, ask for it once and export it for the rest of the session. Creating and
deleting orgs needs a proxy admin key; an org admin's key can update their own
org and manage its members. Never echo the admin key or a newly generated key
back into logs you don't need to.

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
| Create an org | `POST /organization/new` (proxy admin) |
| List or search orgs | `GET /organization/list` |
| See one org with members, teams, budget | `GET /organization/info?organization_id=` |
| Change budget, limits, models, alias | `PATCH /v2/organization/{organization_id}` (v1.95+) |
| Add members, grant org_admin | `POST /organization/member_add` |
| Change a member's org role or budget | `PATCH /organization/member_update` |
| Remove a member | `DELETE /organization/member_delete` |
| Put a team in the org | `litellm-teams`: create or update the team with `organization_id` |
| Delete orgs | `DELETE /organization/delete` (proxy admin) |

## Create an org

`organization_alias` is required; everything else is optional.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/organization/new" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{
    "organization_alias": "acme-research",
    "models": ["gpt-5.5", "claude-sonnet-5-5", "gemini-3.5-flash"],
    "max_budget": 5000,
    "budget_duration": "1mo",
    "rpm_limit": 2000
  }'
```

Show `organization_id` (needed for teams and members), `organization_alias`,
`models`, and the budget. Budget semantics that trip people up:

- `max_budget: 0` means a zero allowance (every request blocked) since v1.103;
  use `null` or omit it for unlimited. Before v1.103, 0 meant unlimited.
- Empty `models` means every proxy model. Only send a list to restrict.
- `budget_id` attaches an existing reusable budget instead of creating one.

Other create fields: `soft_budget` (alert only), `tpm_limit`, `tpd_limit`,
`max_parallel_requests`, `model_max_budget`
(`{"gpt-5.5": {"max_budget": 500, "budget_duration": "30d"}}`),
`model_rpm_limit` / `model_tpm_limit` (`{"gpt-5.5": 100}`), `metadata`, and
`object_permission` (`mcp_servers`, `mcp_access_groups`, `agents`,
`vector_stores`, ...).

## Inspect and find orgs

```bash
# org_alias is a case-insensitive partial match; org_id is exact
curl -sS "$LITELLM_BASE_URL/organization/list?org_alias=acme" \
  -H "Authorization: Bearer $LITELLM_API_KEY"

curl -sS "$LITELLM_BASE_URL/organization/info?organization_id=<organization_id>" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

Both return orgs with `spend`, `models`, `litellm_budget_table`, `members`
(each with `user_id`, `user_role`), and `teams`. Non-admins only see orgs they
belong to.

## Update an org (v1.95+)

`PATCH /v2/organization/{id}` is a JSON merge patch: omitted fields stay,
budget fields and `metadata` clear with `null`, `models` clears with `[]` (all
models), and `organization_alias` cannot be cleared. Unknown fields are a 422,
which is how you catch typos. Accepted fields: `organization_alias`, `models`,
`metadata`, `tpm_limit`, `rpm_limit`, `max_budget`, `soft_budget`,
`max_parallel_requests`, `model_max_budget`, `budget_duration`,
`object_permission`.

```bash
curl -sS -X PATCH "$LITELLM_BASE_URL/v2/organization/<organization_id>" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"max_budget": 8000, "models": ["gpt-5.5", "claude-sonnet-5-5"]}'
```

On older proxies use `PATCH /organization/update` with `organization_id` in the
body; it accepts the same fields plus `model_rpm_limit` / `model_tpm_limit`.

## Members and org admins

This is the only way to make someone `org_admin`; `/user/new` cannot grant it.
Members are named by `user_id` or `user_email`, and an unknown user is created.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/organization/member_add" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{
    "organization_id": "<organization_id>",
    "member": [
      {"user_email": "dana@acme.com", "role": "org_admin"},
      {"user_email": "eli@acme.com", "role": "internal_user"}
    ],
    "max_budget_in_organization": 200
  }'
```

`member` may be one object or a list. The response lists `updated_users` and
`updated_organization_memberships`.

```bash
# change role or per-member org budget
curl -sS -X PATCH "$LITELLM_BASE_URL/organization/member_update" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"organization_id": "<organization_id>", "user_email": "eli@acme.com", "role": "org_admin"}'

# remove from the org (the user account stays)
curl -sS -X DELETE "$LITELLM_BASE_URL/organization/member_delete" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"organization_id": "<organization_id>", "user_email": "eli@acme.com"}'
```

Only a proxy admin can change the org role of someone who is a global
`proxy_admin` or `proxy_admin_viewer`.

## Delete orgs

This is the most destructive call in the gateway. Deleting an org also deletes
every team in it, every org membership, and every key tagged with the org
(team keys inherit the org id). Before asking for confirmation, fetch
`/organization/info` and show the alias, spend, team count and names, and
member count; for key counts run `/key/list?organization_id=` via
`litellm-keys`. On v1.103+ suggest `max_budget: 0` as a reversible freeze
instead. Proceed only on an explicit yes.

```bash
curl -sS -X DELETE "$LITELLM_BASE_URL/organization/delete" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"organization_ids": ["<organization_id>"]}'
```

The response is the list of deleted orgs. Users themselves are not deleted.

## Errors

- **403 "Organizations are only available for LiteLLM Enterprise users"**: no
  license (v1.102+). Nothing to retry; tell the user.
- **401 "Only admins can create orgs"** / **"Only proxy admins can delete
  organizations"**: use a proxy admin key.
- **403 "You do not have access to this organization"**: the caller is not a
  proxy admin or an org admin of this org.
- **400 "User not allowed to give access to all models"**: the caller's own key
  is model-restricted, so it must pass an explicit `models` list.
- **400 "Cannot associate a user_id to this action"** on update: the key has no
  `user_id`; use the master key or an admin key owned by a user.
- **422** on `/v2/organization`: unknown field, negative limit, bad
  `budget_duration`, or trying to null `organization_alias` / `models`.
- **404 "Organization not found"**: check the id with `/organization/list`.
- Anything else: show `detail` / `error.message` verbatim and the likely fix.

Docs: https://docs.litellm.ai/docs/proxy/user_management_heirarchy and
https://docs.litellm.ai/docs/proxy/access_control
