# Team and member fields

Fields accepted by `POST /team/new`, `POST /team/update`, and
`PATCH /team/{team_id}`, plus the member endpoints (LiteLLM v1.103). Send only
what the user asked for. Source of truth: `NewTeamRequest`, `UpdateTeamRequest`,
`TeamMemberAddRequest`, `TeamMemberUpdateRequest` in `litellm/proxy/_types.py`
and `TeamBase` in `litellm/models/team.py`.

## Contents

- Identity and ownership
- Team budgets
- Team rate limits
- Per-member defaults
- Access (models, MCP, agents)
- Routing and safety
- Enterprise-only fields
- Member endpoints
- Bulk member add (older bulk route)

## Identity and ownership

| Field | Type | Notes |
|---|---|---|
| `team_alias` | string | Optional display name; not required. |
| `team_id` | string | Create only; a UUID is generated if omitted. Must be unique. |
| `organization_id` | string | Owning org (orgs are Enterprise). Org limits then cap the team. |
| `members_with_roles` | list | Create only: `[{"user_id" or "user_email", "role": "admin" \| "user"}]`. Afterwards use the member endpoints. |
| `team_member_permissions` | list | Create only; routes non-admin members may call, e.g. `["/key/generate", "/key/update"]`. Change later with `POST /team/permissions_update` (update silently drops it). |
| `metadata` | object | `POST /team/update` replaces it when sent; `PATCH` merges it. |
| `blocked` | bool | Same effect as `/team/block`. |

## Team budgets

| Field | Type | Notes |
|---|---|---|
| `max_budget` | float (USD) | Hard cap across all team keys. `null` means unlimited. |
| `budget_duration` | string | Reset window: `1d`, `7d`, `30d`, `1mo`. |
| `soft_budget` | float | Alert threshold; must be below `max_budget`. |
| `budget_limits` | list | Concurrent windows, each `{"budget_duration": "1d", "max_budget": 20}`. (The endpoint docstring shows `budget_limit`/`time_period`; the model requires `budget_duration`/`max_budget`.) |
| `model_max_budget` | object | Per-model cap every team key inherits unless the key sets its own (v1.103+, Enterprise, 403 otherwise). Each entry needs `max_budget` and `budget_duration`; `tpm_limit`/`rpm_limit` inside it are rejected. `{"gpt-5.5": {"max_budget": 200, "budget_duration": "30d"}}`. |

## Team rate limits

| Field | Type | Notes |
|---|---|---|
| `tpm_limit`, `rpm_limit` | int | Across all team keys. |
| `tpd_limit` | int | Tokens per day; batch submissions are charged here. |
| `model_rpm_limit`, `model_tpm_limit` | object | Per model: `{"claude-sonnet-5-5": 100}`. A key's own per-model limit overrides these. |
| `mcp_rpm_limit` | object | Per MCP server name: `{"github_server": 100}`. |
| `rpm_limit_type`, `tpm_limit_type` | `guaranteed_throughput` \| `best_effort_throughput` | Create only (update silently drops them). Guaranteed raises an error when keys would overallocate the limit. |
| `default_estimated_output_tokens` | int | Tokens reserved for TPM limiting when a request omits `max_tokens`. `default_estimated_output_tokens_per_model` overrides per model. |

## Per-member defaults

These seed every member who has no override of their own.

| Field | Type | Notes |
|---|---|---|
| `team_member_budget` | float | Each member's in-team budget. |
| `team_member_budget_duration` | string | Reset window for it. |
| `team_member_rpm_limit`, `team_member_tpm_limit` | int | Per-member rate limits. |
| `team_member_key_duration` | string | Expiry for keys members create (Enterprise). |
| `default_team_member_models` | list | `allowed_models` given to new members; must be a subset of `models` (v1.83.10+). |

## Access (models, MCP, agents)

| Field | Type | Notes |
|---|---|---|
| `models` | list | Allowed public model names or access groups. Empty means all proxy models. Replaced wholesale on update; use `/team/model/add` and `/team/model/delete` (`{"team_id", "models": [...]}`) for deltas. |
| `access_group_ids` | list | Unified access groups granting models and other resources. |
| `model_aliases` | object | `{"gpt-4o": "gpt-5.5"}`. |
| `object_permission` | object | `mcp_servers`, `mcp_access_groups`, `mcp_tool_permissions`, `mcp_toolsets`, `blocked_tools`, `agents`, `agent_access_groups`, `vector_stores`, `search_tools`, `skills`. `null` or `{}` means none. |
| `allowed_vector_store_indexes` | list | `[{"index_name": "docs", "index_permissions": ["read"]}]`. |

## Routing and safety

| Field | Type | Notes |
|---|---|---|
| `router_settings` | object | Team-level fallbacks, retries, `model_group_retry_policy`. |
| `enforced_file_expires_after`, `enforced_batch_output_expires_after` | object | `{"anchor": "created_at", "days": 30}`. |
| `disable_global_guardrails` | bool | Proxy admin only, Enterprise. |

## Enterprise-only fields

`guardrails`, `policies`, `tags`, `prompts`, `team_member_key_duration`,
`secret_manager_settings`, `allowed_passthrough_routes`,
`disable_global_guardrails`, team `model_max_budget`, and any member with
`role: "admin"`. Without a license the proxy returns an error naming the feature.

## Member endpoints

`POST /team/member_add`: `team_id`, `member` (object or list of
`{"user_id" or "user_email", "role"}`), and optional `max_budget_in_team`,
`budget_duration`, `allowed_models` applied to every member in the request.
Unknown emails create users. Non-admins may only self-join an "available" team
as `user`, without budget or model fields.

`POST /team/member_update`: `team_id`, `user_id` or `user_email`, then any of
`role`, `max_budget_in_team`, `budget_duration`, `tpm_limit`, `rpm_limit`,
`allowed_models` (`[]` removes the per-member restriction), and
`temp_budget_increase` + `temp_budget_expiry` (ISO UTC; both or neither).

`POST /team/member_delete`: `team_id` plus `user_id` or `user_email`. Deletes the
member's keys in that team.

`POST /team/{team_id}/member/{user_id}/reset_spend`: body `{"reset_to": 0}`.
`POST /team/{team_id}/member/{user_id}/reset_budget` (builds after v1.103;
404 on v1.103): no body; returns `budget_source` after the reset.

`GET /team/{team_id}/members/me`: the caller's own membership row (spend,
budget, reset date, role). Useful when the key belongs to a member, not an admin.

`/management/v1/teams/{team_id}/members/bulk_update` rows accept
`user_id` or `user_email` plus `max_budget_in_team`, `tpm_limit`, `rpm_limit`,
`budget_duration`, `allowed_models` (max 500 rows, unknown fields are 422).

## Bulk member add (older bulk route)

`POST /team/bulk_member_add` takes `{"team_id": "...", "members": [{"user_id" or
"user_email", "role"}], "max_budget_in_team": 20}` or `"all_users": true` to add
everyone on the proxy. It returns `results`, `total_requested`,
`successful_additions`, `failed_additions`, and `updated_team`.
