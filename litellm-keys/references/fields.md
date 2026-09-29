# Key fields

Fields accepted by `POST /key/generate`, `POST /key/update`, and
`POST /key/{key}/regenerate` (LiteLLM v1.103). Send only what the user asked
for. Source of truth: `GenerateKeyRequest` / `UpdateKeyRequest` in
`litellm/proxy/_types.py`.

## Contents

- Identity and ownership
- Budgets
- Rate limits
- Access (models, MCP, agents, routes)
- Safety and routing
- Rotation and lifecycle
- Enterprise-only fields
- Admin-only fields

## Identity and ownership

| Field | Type | Notes |
|---|---|---|
| `key_alias` | string | Unique. Can identify the key on update/delete. |
| `user_id` | string | Owner user. Spend also rolls up to the user. |
| `team_id` | string | Owning team. Team budget and model limits still apply. |
| `organization_id` | string | Owning org (Enterprise). |
| `project_id` | string | Enterprise projects. Cannot be reassigned later; `null` on update detaches. |
| `agent_id` | string | Bind the key to a registered agent. |
| `metadata` | object | Free-form. On update, `metadata` replaces the stored object wholesale. |
| `key_type` | `default` \| `llm_api` \| `management` \| `read_only` | Restricts which route families the key can call. Use `llm_api` for app and agent keys that should never touch admin routes. `management` needs a proxy admin (403 otherwise). |

## Budgets

| Field | Type | Notes |
|---|---|---|
| `max_budget` | float (USD) | Hard cap. `null` means unlimited. |
| `budget_duration` | string | Reset window: `1d`, `7d`, `30d`, `1mo`. |
| `soft_budget` | float | Alert threshold; requests still succeed. |
| `budget_limits` | list | Several concurrent windows, each `{"budget_duration": "1d", "max_budget": 5}`. |
| `model_max_budget` | object | Per-model caps (Enterprise): `{"gpt-5.5": {"max_budget": 10, "budget_duration": "30d"}}`. |
| `budget_fallbacks` | object | When a model's budget is exhausted, fall back: `{"gpt-5.5": ["gpt-5.4-mini"]}` (v1.92+). |
| `temp_budget_increase` + `temp_budget_expiry` | float + ISO datetime | Update only. Must be set together. |
| `budget_id` | string | Attach a reusable budget created with `/budget/new`. |

## Rate limits

| Field | Type | Notes |
|---|---|---|
| `rpm_limit`, `tpm_limit` | int | Requests and tokens per minute for the key. |
| `tpd_limit` | int | Tokens per day (v1.103+). |
| `max_parallel_requests` | int | Concurrency cap. |
| `model_rpm_limit`, `model_tpm_limit` | object | Per model: `{"gpt-5.5": 30}`. A key's own per-model limit overrides the team's (v1.103+). |
| `mcp_rpm_limit` | object | Per MCP server: `{"github": 20}` (v1.89+). |
| `tag_rpm_limit` | object | Per request tag (v1.93+). |
| `rpm_limit_type`, `tpm_limit_type` | `guaranteed_throughput` \| `best_effort_throughput` \| `dynamic` | How limits interact with shared capacity. |

## Access (models, MCP, agents, routes)

| Field | Type | Notes |
|---|---|---|
| `models` | list | Public model names or access-group names. Empty list inherits the owner's access. |
| `access_group_ids` | list | Unified access groups (`/v1/access_group`). |
| `aliases` | object | Map a name the client sends to a proxy model: `{"gpt-4o": "gpt-5.5"}`. |
| `object_permission` | object | MCP and agent grants. Keys: `mcp_servers`, `mcp_access_groups`, `mcp_tool_permissions` (`{"server": ["tool"]}`), `mcp_toolsets`, `blocked_tools`, `agents`, `agent_access_groups`, `vector_stores`, `search_tools`, `skills`. |
| `allowed_vector_store_indexes` | list | `[{"index_name": "docs", "index_permissions": ["read"]}]`. |
| `enforced_params` | list | Params every request must include, e.g. `["user"]`. |

## Safety and routing

| Field | Type | Notes |
|---|---|---|
| `guardrails` | list | Guardrail names always applied (Enterprise). |
| `policies` | list | Policy names (Enterprise). |
| `disable_global_guardrails` | bool | Opt this key out of default-on guardrails (Enterprise). |
| `enable_prompt_caching` | bool | Gateway-injected prompt caching (v1.98+). |
| `router_settings` | object | Per-key router overrides (fallbacks, retries). |
| `tags` | list | Request tags for spend attribution and tag routing (Enterprise). |

## Rotation and lifecycle

| Field | Type | Notes |
|---|---|---|
| `duration` | string | Expiry from now: `30d`, `90d`. Omit for no expiry. On update, `null` means never expire. |
| `auto_rotate` | bool | Rotate automatically. Requires `rotation_interval`. |
| `rotation_interval` | string | `30d`, `90d`. |
| `blocked` | bool | Same effect as `/key/block`. |
| `grace_period` | string | Regenerate only: how long the old secret keeps working (`24h`, `2d`). Default can come from `LITELLM_KEY_ROTATION_GRACE_PERIOD`. |
| `new_key` | string | Regenerate only: supply the new secret yourself; must start with `sk-` and be 16+ characters. |

## Enterprise-only fields

`tags`, `guardrails`, `policies`, `prompts`, `disable_global_guardrails`,
`model_max_budget`,
`allowed_passthrough_routes`, `organization_id` (orgs are Enterprise since
v1.102), `project_id`, and the regenerate endpoint (except regenerating the
master key). Without a license the proxy returns an error naming the feature.

## Admin-only fields

`permissions` and `allowed_routes` need a proxy admin (v1.92+).
`throttle_on_budget_exceeded` is rejected for non-admins and only takes effect
when the proxy also has a global throttle percentage configured.

## Service-account keys

`POST /key/service-account/generate` takes the same body, ignores `user_id`,
and creates a key owned by the team (pass `team_id`) rather than a person, so it
survives when people leave. Use it for CI, cron jobs, and production agents.
