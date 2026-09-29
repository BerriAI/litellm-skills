---
name: litellm-users
description: >
  Create, look up, update, invite, and delete internal users on a live LiteLLM
  proxy (AI gateway) with curl. Use this whenever someone wants to onboard a
  person or a batch of people to LiteLLM, give someone a login or an API key,
  send or regenerate an invite link, change a user's role (proxy_admin,
  proxy_admin_viewer, internal_user, internal_user_viewer), set or raise a
  user's personal budget, rate limits, allowed models, or MCP access, reset a
  user's password, or offboard someone and
  revoke everything they own. Also use it for "add alice@acme.com", "make Bob
  an admin", "who are our users", "remove this employee", or bulk CSV imports.
license: MIT
compatibility: Requires curl and python3. Written against LiteLLM v1.103 (September 2026).
metadata:
  author: BerriAI
  version: "2.0"
allowed-tools: Bash(curl:*) Bash(python3:*)
---

# LiteLLM users

An internal user is a person (or SSO identity) who can log in to the Admin UI
and own keys. Each user has a global role, an optional personal budget and
limits, and memberships in teams and organizations. Team membership and
per-team budgets live in the `litellm-teams` skill; org roles such as
`org_admin` live in `litellm-orgs`.

## Connect

Read `LITELLM_BASE_URL` and `LITELLM_API_KEY` from the environment. If either is
missing, ask for it once and export it for the rest of the session. The key must
be a proxy admin key (org admins can manage users inside organizations they
administer). Never echo the admin key or a newly generated key back into logs
you don't need to.

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
| Add one person | `POST /user/new` |
| Add many people (up to 500) | `POST /management/v1/users/bulk` (v1.103+) |
| Send a login / set-password link | `POST /invitation/new` |
| Find users, top spenders | `GET /user/list` |
| See one user with their keys and teams | `GET /user/info?user_id=` |
| Change role, budget, limits, models, password | `POST /user/update` |
| Change the same fields on many users | `POST /user/bulk_update` |
| Offboard people | `POST /user/delete` or `POST /management/v1/users/bulk_delete` (v1.103+) |

Roles: `proxy_admin` (everything), `proxy_admin_viewer` (read everything, write
nothing), `internal_user` (own keys and spend; the usual choice),
`internal_user_viewer` (read own keys and spend). Only a proxy admin can create
or promote someone to `proxy_admin` or `proxy_admin_viewer`.

## Create a user

Ask only for what the request needs; everything is optional, but an email is
what makes the user findable and invitable.

1. `user_email` (must be unique) and `user_alias` (display name)
2. `user_role`, default `internal_user`
3. `teams`: team ids, or `[{"team_id": "...", "user_role": "admin", "max_budget_in_team": 50}]`
4. `organizations`: org ids to join as a plain member (orgs are Enterprise)
5. Personal limits: `max_budget` + `budget_duration`, `models`, `tpm_limit`, `rpm_limit`
6. `auto_create_key` (default `true`) and `send_invite_email`

```bash
curl -sS -X POST "$LITELLM_BASE_URL/user/new" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{
    "user_email": "alice@acme.com",
    "user_alias": "Alice Chen",
    "user_role": "internal_user",
    "teams": ["<team_id>"],
    "max_budget": 100,
    "budget_duration": "30d",
    "models": ["gpt-5.5", "claude-sonnet-5-5"]
  }'
```

Show `user_id` (needed for every later call), `user_email`, `user_role`,
`teams`, `max_budget`, and `key`. With `auto_create_key` left on, `key` is a
personal `sk-...` key returned only now; tell the user to store it, or pass
`"auto_create_key": false` if they only need a login. Do not send `password`:
v1.103 accepts it (checked only against the password policy, 400 on a weak
one) and builds after v1.103 reject it with 422. People should set their own
password through an invite link (below).

For `budget_limits`, per-model budgets, `object_permission` (MCP servers,
agents, vector stores; acts as a ceiling on every key the user holds, v1.96+),
and the admin-only `permissions` field, read `references/fields.md`.

## Create many users (v1.103+)

```bash
curl -sS -X POST "$LITELLM_BASE_URL/management/v1/users/bulk" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"users": [
    {"user_email": "a@acme.com", "teams": ["<team_id>"]},
    {"user_email": "b@acme.com", "user_role": "internal_user_viewer", "auto_create_key": true}
  ]}'
```

Each row takes the `/user/new` fields, except `auto_create_key` defaults to
`false` here and `send_invite_email` is not supported. Rows fail independently:
report every `data[i]` with `success: false` and its `error`, plus
`meta.created` / `meta.failed`. On older proxies, loop over `/user/new`.

## Invite a user to log in

```bash
curl -sS -X POST "$LITELLM_BASE_URL/invitation/new" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"user_id": "<user_id>"}'
```

Build the link from the returned `id`:
`$LITELLM_BASE_URL/ui/onboarding?invitation_id=<id>` and mention `expires_at`.
The person sets their own password there (v1.101+ enforces 12+ characters with
upper, lower, digit, and symbol by default).

## Find and inspect users

```bash
# filters: user_email (partial), search (id or email), role, team, organization_ids,
# user_ids (comma separated); sort_by=spend|created_at|user_email, sort_order=desc
curl -sS "$LITELLM_BASE_URL/user/list?sort_by=spend&sort_order=desc&page_size=25" \
  -H "Authorization: Bearer $LITELLM_API_KEY"

curl -sS "$LITELLM_BASE_URL/user/info?user_id=<user_id>" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

`/user/list` returns `users` (each with `spend`, `max_budget`, `teams`,
`key_count`), `total`, `page`, `total_pages`; `page_size` caps at 100.
`/user/info` returns `user_info`, `keys`, and `teams`. Resolve an email to a
`user_id` with `/user/list?user_email=` before any update or delete.

## Update a user

Send only what changes. Omitted fields keep their value. `max_budget`,
`budget_duration`, and `model_max_budget` can be cleared with `null` (a null
`max_budget` means unlimited); for other fields `null`, `[]`, and `{}` are
ignored, so they cannot be used to clear a list. `metadata`, when sent, replaces
the stored object.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/user/update" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"user_id": "<user_id>", "user_role": "proxy_admin_viewer", "max_budget": 250}'
```

You may identify the user by `user_email` instead of `user_id`, but if no user
has that email the proxy creates a new one; look the email up first. Team
membership cannot be changed here; use `litellm-teams`.

Setting `password` (v1.101+) must pass the policy (12+ characters, upper,
lower, digit, symbol unless the admin relaxed `password_policy_*`), else 400.
On v1.103 that is the only check. Builds after v1.103 also check it against
known breaches, sign the user out everywhere, and force a change at next
login. Prefer an invite link unless the admin insists.

`POST /user/bulk_update` takes `{"users": [<update bodies>]}` or
`{"all_users": true, "user_updates": {...}}` and reports per-user results.

## Delete users

Look each user up first. Show email, role, `key_count`, and teams, then get an
explicit yes. Deleting a user also deletes every key they own (clients start
getting 401), their invitations, and their team and org memberships. Suggest
blocking their keys (`litellm-keys`) if the goal is a temporary lockout.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/user/delete" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"user_ids": ["<user_id>"]}'
```

`/user/delete` stops with 404 at the first unknown id and deletes no users or
keys (users checked before it may already be dropped from team rosters), so
verify every id beforehand. For many users on v1.103+, prefer
`POST /management/v1/users/bulk_delete` with the same body (max 500): unknown or
out-of-scope ids come back as `success: false` rows and the rest are deleted in
one transaction.

## Errors

- **401**: the admin key is wrong or is itself a scoped virtual key.
- **403 "Only proxy admins can create administrative users"**: only a proxy
  admin can grant `proxy_admin` or `proxy_admin_viewer`. Setting `permissions`
  also needs a proxy admin. Org admins can only delete users whose org
  memberships all sit inside orgs they administer.
- **403 "License is over limit"**: the Enterprise license's user seats are used up.
- **409 "User with email ... already exists"**: find the existing user with
  `/user/list?user_email=` and update it instead.
- **422 on `password`** in `/user/new` (builds after v1.103): drop it and send
  an invite.
- **400 password policy** on `/user/new` or `/user/update` (or **breached
  password** on `/user/update`, builds after v1.103): ask for a stronger
  password or use an invite.
- **400 invalid `budget_duration`**: use forms like `30s`, `24h`, `7d`, `1mo`.
- Anything else: show `detail` / `error.message` verbatim and the likely fix.

Docs: https://docs.litellm.ai/docs/proxy/users and
https://docs.litellm.ai/docs/proxy/access_control
