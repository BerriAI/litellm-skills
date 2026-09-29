# Budget and customer fields

Fields and settings behind the budgets skill (LiteLLM v1.103). Source of truth:
`BudgetNewRequest`, `NewCustomerRequest`, `UpdateCustomerRequest` in
`litellm/proxy/_types.py`, `AccessGroupBudgetRequest` in
`litellm/types/proxy/management_endpoints/model_management_endpoints.py`, and
`litellm/proxy/management_endpoints/budget_management_endpoints.py`.

## Contents

- Budget object (`/budget/new`, `/budget/update`)
- Customer fields (`/customer/new`, `/customer/update`)
- Access group budget (`PUT /access_group/{group}/budget`)
- Proxy settings that change budget behavior
- Provider budgets
- Version notes

## Budget object

| Field | Type | Notes |
|---|---|---|
| `budget_id` | string | Generated UUID if omitted on create. Required on update. |
| `max_budget` | float, USD | Hard cap; must be finite and >= 0. `null` = unlimited, `0` = no allowance. |
| `soft_budget` | float, USD | Alert threshold; requests still succeed. |
| `budget_duration` | string | Reset window: number plus `s`, `m`, `h`, `d`, `w`, or `mo` (`30d`, `1mo`). Rejected if unparseable or non-positive. |
| `budget_reset_at` | ISO datetime | Next reset. Computed from `budget_duration` on create and whenever the duration changes, unless you send it. |
| `tpm_limit`, `rpm_limit` | int | Per attached object. |
| `tpd_limit` | int | Tokens per day; batch submissions are charged against it. |
| `max_parallel_requests` | int | Concurrency cap. |
| `model_max_budget` | object | `{"gpt-5.5": {"max_budget": 20, "budget_duration": "1mo", "tpm_limit": 100000, "rpm_limit": 600}}` |

Read-only on responses: `created_at`, `created_by`, `updated_at`,
`updated_by`, plus `allowed_models`, `temp_budget_increase`,
`temp_budget_expiry` when the row backs a team membership.

`POST /budget/update` is a merge: only fields present in the body are written,
and an explicit `null` clears that column. `POST /budget/info` takes
`{"budgets": ["id", ...]}` and returns the rows. `GET /budget/settings?budget_id=`
returns each editable field with its current value and description.
`GET /management/v1/budgets` (v1.96+, admin roles) pages the table: `page`,
`page_size` (default 50, max 100), `sort` (comma list of `budget_id`,
`max_budget`, `tpm_limit`, `rpm_limit`, `tpd_limit`, `created_at`, `-` prefix
for descending; default `-created_at`), `q` (substring of `budget_id`), and
filters `filter[budget_duration][in|is_null]`,
`filter[max_budget][gte|lte|is_null]`, `filter[created_at][gte|lte]`. It
returns limits only, not spend.

## Customer fields

`/customer/new`:

| Field | Notes |
|---|---|
| `user_id` | Required. The id callers send as `user`. |
| `alias` | Display name. |
| `budget_id` | Attach an existing tier. Cannot be combined with `max_budget`. |
| `max_budget`, `soft_budget`, `budget_duration`, `tpd_limit`, `budget_reset_at` | Creates a private budget row for this customer. `tpm_limit`, `rpm_limit`, `model_max_budget`, `max_parallel_requests` are accepted but documented as not enforced for customers. |
| `blocked` | `true` rejects every request with this id. |
| `spend` | Seed the spend counter. |
| `allowed_model_region` | `eu` or `us`; routes only to deployments in that region. |
| `default_model` | Used when no model in the region fits. Must exist on the proxy (422 otherwise). |
| `object_permission` | `{"mcp_servers": [...], "mcp_access_groups": [...], "mcp_tool_permissions": {...}, "vector_stores": [...], "agents": [...], "agent_access_groups": [...]}` |

`/customer/update` accepts only `user_id`, `alias`, `blocked`, `max_budget`,
`budget_id`, `allowed_model_region`, `default_model`, `object_permission`.
Unknown fields such as `budget_duration` are silently ignored, and a
`max_budget` of `0` is dropped as a default value. `max_budget` writes to the
budget row the customer already points at (creating one if it has none), so on
a shared tier it changes every customer on that tier.

Customer responses include `spend`, `blocked`, `budget_id`, and the nested
`litellm_budget_table` (with `budget_reset_at`). A customer with no budget row
is governed by the default below.

Defaults for customers without their own budget:

- `litellm_settings.max_end_user_budget_id: "<budget_id>"` applies that tier to
  every customer with no budget, including ids never seen before. It is cached
  for about 60 seconds. The old float `max_end_user_budget` is no longer
  enforced.
- A key's `end_user_budget_id` (v1.103+, set on `/key/generate` or
  `/key/update`) overrides that default for customers calling through that key.

## Access group budget

Body fields: `budget_id` (link an existing row), `max_budget` (>= 0),
`soft_budget` (>= 0), `budget_duration`. At least one is required (400); any
other field is a 422 because rate limits are not enforced per access group.
When the group already has a budget, `max_budget` and friends update that row
in place, so a `budget_id` shared with other objects changes for them too.
`DELETE` unlinks the budget and leaves the budget row. Group spend is shared by
every key that can reach any model in the group, and `/access_group/list`
returns `spend` and `budget` per group.

## Proxy settings that change budget behavior

| Setting | Where | Effect |
|---|---|---|
| `budget_exceeded_status_code` | `litellm_settings` | HTTP status for `budget_exceeded`. Added after v1.103 with a default of 422; v1.103 and earlier always return 429. |
| `budget_rollover` | `litellm_settings` | v1.100+. Carry over-cap spend into the next window. Default false. |
| `budget_reset_time` | `litellm_settings` | v1.95+. `"HH:MM"` wall-clock time (in the configured timezone) for day/week/month resets. |
| `budget_exceeded_throttle_percentage` | `litellm_settings` | 0 to 1. With a key's `throttle_on_budget_exceeded: true` (proxy admin only) and a TPM/RPM limit on the key, an over-budget key runs at that fraction of its limits instead of failing. |
| `max_end_user_budget_id` | `litellm_settings` | Default customer tier (above). |
| `apply_user_budget_to_team_keys` | `general_settings` | v1.97+. Enforce a user's personal `max_budget` on their team keys too. Default false. |
| `fail_closed_budget_enforcement` | `general_settings` | Reject when spend cannot be read, and (v1.101+) reject up front when the worst-case estimate exceeds the remaining budget. |
| `disable_budget_reservation` | `general_settings` | Turns off in-flight cost reservation. Only for leaked-reservation false positives. |

## Provider budgets

Set in config, not via API:

```yaml
router_settings:
  provider_budget_config:
    openai:
      budget_limit: 100      # USD per time_period
      time_period: 1d
```

`GET /provider/budgets` returns `{"providers": {"openai": {"budget_limit",
"time_period", "spend", "budget_reset_at"}}}`; it errors when no provider
budget config is set. Docs: https://docs.litellm.ai/docs/proxy/provider_budget_routing

## Version notes

- v1.90: `/customer/daily/activity` admin-only.
- v1.93: release notes call over-budget keys "throttled"; in source this is the
  opt-in `throttle_on_budget_exceeded` path above, and keys without it are
  still rejected.
- v1.94.0: user budgets were enforced on team keys (locked some users out);
  reverted in v1.94.1. v1.97 added the opt-in flag instead.
- v1.95: `budget_reset_time`; word-form durations no longer collapse to daily.
- v1.96: `GET /management/v1/budgets`.
- v1.100: access group budgets, `budget_rollover`, per-window spend table.
- v1.101: `fail_closed_budget_enforcement` rejects on the worst-case estimate.
- v1.103: org and project `max_budget: 0` means zero, budgets re-checked on
  router fallback targets, per-key `end_user_budget_id`.
