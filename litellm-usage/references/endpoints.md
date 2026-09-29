# Usage endpoint reference

Field-level detail for the usage endpoints (LiteLLM v1.103). Read the section
you need. Source of truth: `litellm/proxy/management_endpoints/common_daily_activity.py`,
`litellm/types/proxy/management_endpoints/common_daily_activity.py`, and
`litellm/proxy/spend_tracking/spend_management_endpoints.py`.

## Contents

- Daily activity: query parameters
- Daily activity: response fields
- Tag spend (`/global/spend/tags`)
- Per-user spend in a team (`/team/spend/by_user`)
- Request logs (`/spend/logs/v2`)
- Spend reports (Enterprise)
- Gateway request counts (`/gateway/daily/activity`)
- Tool spend (`/v1/tool/spend`)
- Capture rate (`/spend/capture_rate`, builds after v1.103)
- Endpoints to avoid

## Daily activity: query parameters

| Param | Endpoints | Notes |
|---|---|---|
| `start_date`, `end_date` | all | `YYYY-MM-DD`, UTC day buckets, inclusive. Required; missing gives 400. |
| `model` | all | Exact `model` value as logged (the deployment model, not always the public name). |
| `api_key` | all | Key hash (the `token` from `/key/list`). |
| `page`, `page_size` | paginated only | Defaults: user 50 (max 1000); team, org, tag, customer, agent 10 (no max). |
| `user_id` | user | Single id. Omit for the proxy-wide view (admin roles only). |
| `team_ids`, `exclude_team_ids` | team | Comma lists. |
| `organization_ids`, `exclude_organization_ids` | org | Comma lists. |
| `tags` | tag | Comma list. No exclude. |
| `end_user_ids`, `exclude_end_user_ids` | customer | Comma lists. `/end_user/daily/activity` is a hidden alias. |
| `agent_ids`, `exclude_agent_ids` | agent | Comma lists. Needs the `agents` feature enabled for the caller. |
| `timezone` | user, user aggregated, team aggregated | Minutes, `Date.getTimezoneOffset()` sign (480 = PST). |
| `include_current_utc_day` | user, user aggregated | With `timezone`, extends a range ending on the caller's local today to today's UTC bucket. Historical ranges never move. |

Aggregated variants: `/user/daily/activity/aggregated` and
`/team/daily/activity/aggregated` (v1.99+). No `page`/`page_size`. The team one
rejects ranges over 400 days and malformed dates with 400 and includes
`breakdown.entities` per team; the user one has no entity breakdown. No other
entity has an aggregated route.

## Daily activity: response fields

```json
{
  "results": [
    {
      "date": "2026-09-27",
      "metrics": {"spend": 12.41, "prompt_tokens": 812000, "completion_tokens": 96000,
                  "total_tokens": 908000, "api_requests": 1430, "successful_requests": 1422,
                  "failed_requests": 8, "cache_read_input_tokens": 120000, "...": 0},
      "breakdown": {
        "models": {"gpt-5.5": {"metrics": {"spend": 9.1, "...": 0}, "metadata": {}, "api_key_breakdown": {}}},
        "api_keys": {"<sha256>": {"metrics": {"...": 0}, "metadata": {"key_alias": "billing-agent-prod", "team_id": "...", "user_id": "...", "user_email": "...", "key_exists": true}}},
        "entities": {"<team_id>": {"metrics": {"...": 0}, "metadata": {"team_alias": "search"}}}
      }
    }
  ],
  "metadata": {"total_spend": 12.41, "total_api_requests": 1430, "page": 1, "total_pages": 3, "has_more": true}
}
```

`metrics` (SpendMetrics): `spend`, `flat_cost`, `prompt_tokens`,
`completion_tokens`, `total_tokens`, `cache_read_input_tokens`,
`cache_creation_input_tokens`, `compression_saved_tokens`,
`compression_savings_spend`, `prompt_caching_savings_spend`,
`gateway_injected_caching_savings_spend`, `autorouter_savings_spend`,
`successful_requests`, `failed_requests`, `api_requests`,
`total_response_time_ms`, `timed_requests` (average latency is
`total_response_time_ms / timed_requests`). `flat_cost` is non-zero only with
PTU cost attribution enabled.

`breakdown` keys: `models`, `model_groups`, `providers` (`unknown` when not
recorded), `endpoints`, `api_keys`, `mcp_servers` (keyed by namespaced MCP tool
name), `entities`. Every entry except `api_keys` also carries
`api_key_breakdown`. Entity metadata: team `team_alias`, org
`organization_alias`, customer `alias`, agent `agent_name`, user `user_email`
and `user_alias`.
Rows without an entity id are grouped under `Unassigned`.

`metadata` (DailySpendMetadata): `total_spend`, `total_flat_cost`,
`total_prompt_tokens`, `total_completion_tokens`, `total_tokens`,
`total_api_requests`, `total_successful_requests`, `total_failed_requests`,
`total_cache_read_input_tokens`, `total_cache_creation_input_tokens`,
`total_compression_saved_tokens`, `total_compression_savings_spend`,
`total_prompt_caching_savings_spend`,
`total_gateway_injected_caching_savings_spend`,
`total_autorouter_savings_spend`, `total_response_time_ms`,
`total_timed_requests`, `page`, `total_pages`, `has_more`. On paginated
endpoints every `total_*` covers only the rows on that page.

Daily spend rows only ever accumulate; budget resets do not touch them. That is
why a user's month of daily activity can exceed the `spend` shown by
`/user/info`, which is the resettable budget counter.

## Tag spend

`GET /global/spend/tags?start_date=&end_date=[&tags=a,b]` reads the
`DailyTagSpend` view over spend logs. Both dates are required. Returns
`{"spend_per_tag": [{"name", "spend", "log_count"}]}` sorted by spend, spend
rounded to 4 decimals. Unfiltered it includes `User-Agent:` tags. Because it
reads spend logs, it only covers what log retention keeps; `/tag/daily/activity`
reads the daily table and does not age out.

## Per-user spend in a team

`GET /team/spend/by_user?team_ids=<id>[,<id>]&start_date=&end_date=` (v1.101+).
`team_ids` required; range at most 400 days. Response
`{"start_date", "end_date", "results": [{team_id, team_alias, user_id,
user_email, user_alias, spend, prompt_tokens, completion_tokens, total_tokens,
api_requests, successful_requests, failed_requests}]}` ordered by spend. Team
admins and members with the `/team/daily/activity` permission see every user;
other members see only their own row.

## Request logs

`GET /spend/logs/v2`. `start_date` and `end_date` required, as `YYYY-MM-DD` or
`YYYY-MM-DD HH:MM:SS` (UTC). The window is `startTime >= start AND startTime <=
end`, so a bare end date stops at 00:00 of that day.

| Param | Notes |
|---|---|
| `page`, `page_size` | default 1 and 50, `page_size` max 1000 |
| `api_key`, `key_alias`, `user_id`, `team_id`, `end_user` | exact filters |
| `model`, `model_id`, `model_group` | exact filters |
| `status_filter` | `success` or `failure` |
| `error_code`, `error_message` | code exact (`"429"`), message substring |
| `min_spend`, `max_spend` | USD bounds |
| `session_id` | substring |
| `request_id` | one request |
| `cache_hit_filter` | `hit` or `miss` |
| `span_type` | `llm`, `agent`, `mcp`, `batch` (builds after v1.103; v1.103 ignores it) |
| `sort_by` | `startTime` (default), `endTime`, `spend`, `total_tokens`, `request_duration_ms`, `model`, `ttft_ms` |
| `sort_order` | `desc` (default) or `asc` |
| `exclude_internal_health_checks` | `true` to hide health checks |

Response: `{"data": [...], "total", "page", "page_size", "total_pages"}`.
Non-admins only see their own and permitted teams' rows.

## Spend reports (Enterprise)

| Path | Scope param | Who |
|---|---|---|
| `GET /key/spend/report` | `api_key` (hash or `sk-`) | admins any; others their own key |
| `GET /user/spend/report` | `internal_user_id` | admins any; others themselves |
| `GET /team/spend/report` | `team_id` | admins any; others their key's team |
| `GET /organization/spend/report` | `organization_id` | admins any; org admins their orgs |
| `GET /global/spend/report` | `group_by=team\|customer\|api_key`, plus `api_key`, `internal_user_id`, `team_id`, `customer_id` | admin |

The four scoped reports (v1.97+) require `start_date`/`end_date`, cap the range
at 366 days, and return rows `{api_key, total_cost, total_input_tokens,
total_output_tokens, model_details: [{model, total_cost, total_input_tokens,
total_output_tokens}]}` (org rows add `team_id` per model). They read spend
logs, so retention limits apply.

## Gateway request counts

`GET /gateway/daily/activity?start_date=&end_date=` (v1.97+, proxy admin or
admin viewer; dates default to the last 30 days). Counts what the proxy
answered at the HTTP edge, including requests that never reached logging:
`{total_successful_requests, total_failed_requests, by_date: [{date,
successful_requests, failed_requests}], by_route: [{category, route,
successful_requests, failed_requests}]}`. No per-key or per-team dimension.

## Tool spend

`GET /v1/tool/spend?start_date=&end_date=` (admin roles). Dates default to the
last 30 days. `by_tool` lists up to 100 tools by spend (`tool_name`, `spend`,
`call_count`, `total_tokens`) and `daily` has per-day rows for those tools. A
request that invoked several tools counts its full spend toward each, so the
per-tool numbers do not add up to total spend. v1.94 and v1.95 capped the
window at 30 days.

## Capture rate (builds after v1.103)

v1.103 has no such route and returns 404. On builds after v1.103,
`GET /spend/capture_rate?provider=openai&start_date=&end_date=[&threshold=0.9&project_ids=...]`
compares LiteLLM's captured spend with the provider's own bill per UTC day.
Admin only, needs `OPENAI_ADMIN_KEY` on the proxy, range under 180 days.

## Endpoints to avoid

- `/global/activity`: hidden from the schema, scans raw spend logs, and returns
  dates as `"Sep 27"` strings sorted alphabetically. Use daily activity.
- `/global/activity/cache_hits`: hidden, UI-only; fine for a quick cache hit
  ratio, but its shape may change.
- `/spend/logs` (v1): deprecated and unpaginated. Use `/spend/logs/v2`.
- `/global/spend/*` (keys, teams, models, logs): legacy views over spend logs.
