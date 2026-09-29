# User fields

Fields accepted by `POST /user/new`, `POST /user/update`, and each row of
`POST /management/v1/users/bulk` (LiteLLM v1.103). Send only what the user asked
for. Source of truth: `NewUserRequest` / `UpdateUserRequest` in
`litellm/proxy/_types.py`.

## Contents

- Identity and role
- Membership (create only)
- Budgets
- Rate limits
- Access (models, MCP, agents)
- Key created with the user
- Update-only fields and clearing rules
- Restricted fields

## Identity and role

| Field | Type | Notes |
|---|---|---|
| `user_id` | string | Optional on create; a UUID is generated if omitted. Must be unique (409 otherwise). |
| `user_email` | string | Unique (409 on duplicate). On update, can identify the user instead of `user_id`. |
| `user_alias` | string | Display name. |
| `user_role` | `proxy_admin` \| `proxy_admin_viewer` \| `internal_user` \| `internal_user_viewer` | `org_admin` is not accepted here; grant it with `/organization/member_add`. |
| `sso_user_id` | string | Link to an SSO identity (create only). |
| `metadata` | object | Free-form. On update, a sent object replaces the stored one. |

## Membership (create only)

| Field | Type | Notes |
|---|---|---|
| `teams` | list | Team ids, or objects `{"team_id": "t1", "user_role": "user" \| "admin", "max_budget_in_team": 20}`. If omitted, proxy-configured default teams apply. Assigning `admin` needs Enterprise. |
| `organizations` | list | Org ids; the user joins as a plain member. Orgs need Enterprise (v1.102+). |
| `team_id` | string | Deprecated single-team form of `teams`. |

## Budgets

| Field | Type | Notes |
|---|---|---|
| `max_budget` | float (USD) | Personal cap across all the user's keys. `null` means unlimited. If omitted for an `internal_user`, the proxy's `max_internal_user_budget` default applies. |
| `budget_duration` | string | Reset window: `30s`, `24h`, `7d`, `30d`, `1mo`. |
| `budget_limits` | list | Several concurrent windows, each `{"budget_duration": "1d", "max_budget": 5}`. (The endpoint docstring shows `budget_limit`/`time_period`; the model actually requires `budget_duration`/`max_budget`.) |
| `model_max_budget` | object | Per-model caps (Enterprise on `/user/new`, since it also sets the auto-created key): `{"gpt-5.5": {"max_budget": 10, "budget_duration": "30d"}}`. |
| `budget_fallbacks` | object | When a model's `model_max_budget` is exhausted, try others in order: `{"gpt-5.5": ["gpt-5.4-mini"]}`. |
| `spend` | float | Overwrites tracked spend. Rarely what anyone wants; confirm first. |

## Rate limits

| Field | Type | Notes |
|---|---|---|
| `tpm_limit`, `rpm_limit` | int | Per-minute limits across the user's keys. |
| `max_parallel_requests` | int | Concurrency cap; excess returns 429. |
| `model_rpm_limit`, `model_tpm_limit` | object | Per model: `{"gpt-5.5": 30}`. |
| `mcp_rpm_limit`, `tag_rpm_limit` | object | Stored on the user but enforced only for keys and teams. Set them there instead. |

## Access (models, MCP, agents)

| Field | Type | Notes |
|---|---|---|
| `models` | list | Public model names or access groups. Empty means no personal restriction. `["no-default-models"]` blocks all models outside the user's teams. |
| `aliases` | object | Map a requested name to a proxy model: `{"gpt-4o": "gpt-5.5"}`. |
| `object_permission` | object | `mcp_servers`, `mcp_access_groups`, `mcp_tool_permissions` (`{"github_server": ["list_issues"]}`), `mcp_toolsets`, `blocked_tools`, `agents`, `agent_access_groups`, `vector_stores`, `search_tools`, `skills`, `models`. Since v1.96 the MCP grants act as a ceiling on every key the user holds. `{}` or `null` on update removes it. A non-admin cannot change their own. |
| `policies` | list | Policy names to apply (Enterprise). |
| `prompts` | list | Prompt ids the user may use. |
| `allowed_cache_controls` | list | e.g. `["no-cache", "no-store"]`. |

## Key created with the user

`/user/new` creates a personal key unless `auto_create_key` is `false`. These
fields shape that key: `key_alias`, `duration` (expiry such as `90d`),
`send_invite_email` (create only; uses the proxy's email integration). The
bulk endpoint defaults `auto_create_key` to `false` and rejects
`send_invite_email`.

## Update-only fields and clearing rules

| Field | Notes |
|---|---|
| `password` | Admin-set password (v1.101+ policy: 12+ chars, upper, lower, digit, symbol; tunable via `general_settings.password_policy_*`; 400 on a weak one). v1.103 accepts it on `/user/new` and `/user/update` with only the policy check. Builds after v1.103 reject it on `/user/new` (422) and, on update, also run a breach check, revoke the user's UI sessions, and force a change at next login. Prefer `POST /invitation/new`. |
| `user_id` or `user_email` | One is required. An unmatched `user_email` creates a new user. |

Clearing: `max_budget`, `budget_duration`, and `model_max_budget` accept `null`.
Every other field ignores `null`, `[]`, and `{}` (so `"models": []` does not
lift a model restriction; set an explicit list instead). `object_permission`
is the exception and clears with `{}` or `null`.

## Restricted fields

- `permissions`: proxy admin only (403 otherwise).
- Non-admins updating themselves cannot change `max_budget`,
  `model_max_budget`, `soft_budget`, `spend`, or `object_permission` (403).
- `guardrails` and `blocked` exist on the model but are not enforced for users;
  block a user's keys with `litellm-keys` instead.
