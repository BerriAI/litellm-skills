---
name: litellm-teams
description: >
  Manage teams and team membership on a live LiteLLM proxy (AI gateway) with
  curl: add or remove people, set per-member budgets, rate limits, and model
  access, see per-member spend, unblock a member who hit their budget, and
  create, update, block, or delete teams with shared budgets and model
  allowlists. Use this whenever someone says "add Priya to the ML team", "give
  everyone on data-eng $50 a month", "remove Sam from the team", "why is this
  member blocked", "who spent the most on team X", "make a team for the support
  bots", "let this team use claude-sonnet-5-5", "freeze this team", or mentions
  a team_id, team_alias, team admin, or team budget, including synonyms like
  "project group" or "squad".
license: MIT
compatibility: Requires curl and python3. Written against LiteLLM v1.103 (September 2026).
metadata:
  author: BerriAI
  version: "2.0"
allowed-tools: Bash(curl:*) Bash(python3:*)
---

# LiteLLM teams

A team groups people and keys under one budget, model allowlist, and set of
rate limits. Every member also gets a per-member budget inside the team, either
the team default (`team_member_budget`) or their own override. Keys created
with a `team_id` are capped by the team (see `litellm-keys`).

## Connect

Read `LITELLM_BASE_URL` and `LITELLM_API_KEY` from the environment. If either is
missing, ask for it once and export it for the rest of the session. The key must
be a proxy admin key, or the key of a team admin or org admin for teams they
manage. Never echo the admin key or a newly generated key back into logs you
don't need to.

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
| Add people (with optional per-member budget) | `POST /team/member_add` |
| Change a member's role, budget, limits, models | `POST /team/member_update` |
| Set limits for many members at once | `POST /management/v1/teams/{team_id}/members/bulk_update` (v1.103+) |
| Remove people | `POST /team/member_delete`, or `.../members/bulk_delete` (v1.103+) |
| Unblock a member who hit their budget | `POST /team/{team_id}/member/{user_id}/reset_spend` (v1.100+) |
| Put a member back on the team default budget | `POST /team/{team_id}/member/{user_id}/reset_budget` (builds after v1.103) |
| Spend per member | `GET /team/spend/by_user` (v1.101+) |
| Create a team | `POST /team/new` |
| See one team, its members and keys | `GET /team/info?team_id=` |
| Find teams | `GET /v2/team/list` |
| Change team budget, models, limits | `PATCH /team/{team_id}` (v1.93+), `POST /team/update`, `/team/model/add` |
| Freeze or unfreeze all of a team's keys | `POST /team/block`, `POST /team/unblock` |
| Delete teams | `POST /team/delete` |

Member roles are `admin` and `user`. Assigning `admin` needs Enterprise; without
it, only proxy admins (and org admins for their org's teams) manage members.

## Add people and set per-member budgets

Resolve the team id first (`/v2/team/list?team_alias=`). Members are named by
`user_id` or `user_email`; an unknown email creates the user.
`max_budget_in_team`, `budget_duration`, and `allowed_models` apply to every
member in the request and override the team default for them.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/team/member_add" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"team_id": "<team_id>",
       "member": [{"user_email": "priya@acme.com", "role": "user"},
                  {"user_id": "<user_id>", "role": "user"}],
       "max_budget_in_team": 50, "budget_duration": "30d"}'
```

`member` may also be a single object. Adding someone already on the team
returns 400; in a list, duplicates are skipped. Show `updated_users` and
`updated_team_memberships`. For large imports see `/team/bulk_member_add` in
`references/fields.md`.

To change one member later (role, `max_budget_in_team`, `budget_duration`,
`tpm_limit`, `rpm_limit`, `allowed_models`; `[]` removes a model restriction),
or to give a temporary bump with `temp_budget_increase` plus
`temp_budget_expiry` (ISO UTC, both required together):

```bash
curl -sS -X POST "$LITELLM_BASE_URL/team/member_update" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"team_id": "<team_id>", "user_email": "priya@acme.com", "max_budget_in_team": 100, "rpm_limit": 30}'
```

Many members at once (v1.103+): `/management/v1/teams/<team_id>/members/bulk_update`
with `{"members": [{"user_id": "...", "max_budget_in_team": 10}]}`. Each row is
a merge patch (omitted stays, `null` clears, clearing the last limit returns the
member to the team default); roles are not changed there.

For a default that covers everyone, set the team's `team_member_budget`,
`team_member_budget_duration`, `team_member_rpm_limit`, `team_member_tpm_limit`.
Members with their own override keep it. On builds after v1.103,
`reset_budget` moves one member back onto the default without touching spend;
v1.103 returns 404 there, so clear the member's limits with a `null` row in
`bulk_update` instead.

## Remove people

Confirm first: removing a member also deletes the keys they hold in this team,
so anything using them starts failing. Their account and other teams stay.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/team/member_delete" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"team_id": "<team_id>", "user_email": "sam@acme.com"}'
```

Many people (v1.103+): `POST /management/v1/teams/<team_id>/members/bulk_delete`
with `{"members": [{"user_id": "..."}, {"user_email": "..."}]}`; report `success: false` rows.

## Member spend and budget resets

```bash
curl -sS -H "Authorization: Bearer $LITELLM_API_KEY" \
  "$LITELLM_BASE_URL/team/spend/by_user?team_ids=<team_id>&start_date=2026-09-01&end_date=2026-09-29"

curl -sS -X POST "$LITELLM_BASE_URL/team/<team_id>/member/<user_id>/reset_spend" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"reset_to": 0}'
```

`spend/by_user` needs `YYYY-MM-DD` dates (max 400 days) and comma-separated
`team_ids`. `/team/info` lists `team_memberships` with each member's `spend`
(builds after v1.103 also return `budget_source`: `team_default`, `custom`,
`none`). In-team spend is tracked
apart from personal and team spend, so `reset_spend` is the only way to clear
it (non-admins cannot reset their own).

## Create a team

Everything is optional, including `team_alias` (recommended). Common fields:
`models`, `max_budget` + `budget_duration`, `tpm_limit` / `rpm_limit`,
`organization_id`, `members_with_roles`, and member defaults
(`team_member_budget`, `team_member_budget_duration`, `default_team_member_models`).

```bash
curl -sS -X POST "$LITELLM_BASE_URL/team/new" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"team_alias": "data-eng",
       "models": ["gpt-5.5", "claude-sonnet-5-5", "gemini-3.5-flash"],
       "max_budget": 1000, "budget_duration": "1mo",
       "team_member_budget": 50, "team_member_budget_duration": "1mo",
       "members_with_roles": [{"user_email": "lead@acme.com", "role": "user"}]}'
```

Show `team_id` (needed for keys and members), `team_alias`, `models`,
`max_budget`. For the full field list (per-model limits, `budget_limits`,
MCP access, router settings, Enterprise-only fields) read `references/fields.md`.

## Inspect and find teams

```bash
curl -sS "$LITELLM_BASE_URL/team/info?team_id=<team_id>" -H "Authorization: Bearer $LITELLM_API_KEY"
# filters: team_alias (partial), search, organization_id, user_id; page_size<=100
curl -sS "$LITELLM_BASE_URL/v2/team/list?team_alias=data" -H "Authorization: Bearer $LITELLM_API_KEY"
```

`/team/info` returns `team_info` (limits, `spend`, `members_with_roles`),
`keys`, and `team_memberships`; `/v2/team/list` returns `teams`, `total`, `total_pages`.

## Update a team

Both forms leave omitted fields untouched. For `metadata`, prefer
`PATCH /team/{team_id}` (v1.93+), which merges keys (`"key": null` deletes one);
`POST /team/update` (body includes `team_id`) replaces `metadata` when sent, and
before v1.101 a partial update could wipe it.

```bash
curl -sS -X PATCH "$LITELLM_BASE_URL/team/<team_id>" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"max_budget": 2000, "rpm_limit": 600}'
```

`models` replaces the whole list; to add or drop a few, use
`/team/model/add` or `/team/model/delete` with `{"team_id", "models": [...]}`.
`soft_budget` must stay below `max_budget`.

## Block, unblock, delete

`/team/block` and `/team/unblock` take `{"team_id": "<team_id>"}` and stop or
resume every key on the team, losing nothing. Suggest this before deleting.
Deletion is permanent and deletes every key on the team: show alias, member
count, key count, and spend, and get an explicit yes.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/team/delete" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"team_ids": ["<team_id>"]}'
```

The response lists `deleted_teams`. Users stay; only their memberships go.

## Errors

- **401**: bad admin key. **403 "User not proxy admin OR team admin"**: the
  caller doesn't manage this team (proxy admin viewers cannot write).
- **400 "Assigning team admins is a premium feature"**: `role: "admin"` needs
  Enterprise. So do team `guardrails`, `policies`, `tags`, `prompts`,
  `team_member_key_duration`, `secret_manager_settings`,
  `allowed_passthrough_routes`, and (403) team `model_max_budget`.
- **400 "User already in team"**: use `/team/member_update` instead.
- **400 soft_budget / max_budget**: non-negative, and `soft_budget < max_budget`.
- **403 "License is over limit"**: the license's team count is used up.
- Anything else: show `detail` / `error.message` verbatim and the likely fix.

Docs: https://docs.litellm.ai/docs/proxy/team_budgets and
https://docs.litellm.ai/docs/proxy/users
