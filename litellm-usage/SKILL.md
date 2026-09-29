---
name: litellm-usage
description: >
  Report spend, tokens, request counts, failures, and cost attribution from a
  live LiteLLM proxy (AI gateway) with curl or a bundled python3 script. Use
  this whenever someone asks what LiteLLM cost this month or last week, how
  many tokens or requests went through, which team, user, key, customer, agent,
  model, provider, MCP server, or tag spent the most, who the top spenders are,
  what a batch job or tagged workload cost, why requests failed on a given day,
  or wants daily usage tables, chargeback numbers, a spend report, or the raw
  request logs behind a number. Also use it for "show me usage", "cost
  breakdown", "spend by team", "which key is burning money", and "how much did
  job:nightly-eval cost", even when the user never says "LiteLLM usage".
license: MIT
compatibility: Requires curl and python3. Written against LiteLLM v1.103 (September 2026).
metadata:
  author: BerriAI
  version: "2.0"
allowed-tools: Bash(curl:*) Bash(python3:*)
---

# LiteLLM usage

LiteLLM rolls every request into daily spend tables (one row per date, entity,
key, model, provider, endpoint, MCP tool) and keeps per-request spend logs. This
skill reads both. It never changes anything on the proxy.

## Connect

Read `LITELLM_BASE_URL` and `LITELLM_API_KEY` from the environment. If either is
missing, ask for it once and export it for the rest of the session. The key
should be a proxy admin or proxy admin viewer key for proxy-wide numbers; any
other key only sees its own user, its teams, or its own keys (see Scoping).
Never echo the admin key or a newly generated key back into logs you don't need to.

```bash
curl -sS "$LITELLM_BASE_URL/health/readiness/details" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

Skip it if you already checked this proxy earlier in the session. It confirms
the URL and key work and returns `litellm_version`. Features
below that changed recently name the version they arrived in; if the proxy is
older, say so instead of guessing.

## Pick the operation

| The user wants to | Use |
|---|---|
| Daily table for the whole proxy, a user, team, org, tag, customer, or agent | `scripts/usage_report.py` (wraps the calls below) |
| Totals for one period, no pagination | `GET /user/daily/activity/aggregated`, `GET /team/daily/activity/aggregated` (v1.99+) |
| Same for tags, customers, agents | `GET /{tag,customer,agent}/daily/activity` (paginated) |
| Same for orgs (Enterprise, v1.102+) | `GET /organization/daily/activity` (paginated) |
| Top models, keys, providers, MCP servers | `breakdown.*` of the daily activity response (`--top`) |
| Top spending users or keys (budget counters) | `GET /user/list?sort_by=spend&sort_order=desc`, `GET /key/list?sort_by=spend&sort_order=desc` |
| Per-user spend inside a team | `GET /team/spend/by_user?team_ids=` (v1.101+) |
| Cost of a job or workload | request tags: `/tag/daily/activity`, `/global/spend/tags` |
| The requests behind a number | `GET /spend/logs/v2` |
| Success vs failure by route, deployment wide | `GET /gateway/daily/activity` (admin, v1.97+) |
| Per-key/user/team/org report with per-model detail | `GET /{key,user,team,organization}/spend/report` (Enterprise, v1.97+) |

Every date is a UTC day in `YYYY-MM-DD`. Default to the current month when the
user gives no range. `start_date` and `end_date` are required on every daily
activity endpoint; leaving either out returns 400.

## Quick report

The script lives in this skill's directory; run it from there or give its full
path.

```bash
python3 scripts/usage_report.py                                  # whole proxy, this month
python3 scripts/usage_report.py --by team --ids <team_id>,<team_id> --top models,api_keys
python3 scripts/usage_report.py --by tag --ids job:nightly-eval --start 2026-09-01 --end 2026-09-28
python3 scripts/usage_report.py --by customer --top entities --limit 20 --json
```

`--by` is `overall|user|team|org|tag|customer|agent`; `--ids` is a comma list;
`--model` and `--key-hash` filter; `--top` ranks any of `models`,
`model_groups`, `providers`, `endpoints`, `api_keys`, `mcp_servers`, `entities`.
It prints Date | Requests | Tokens | Spend with a totals row, marks days that
had failed requests, and uses the `/aggregated` endpoint when one exists,
otherwise it pages until `has_more` is false and merges rows by date. Prefer it
over hand-rolled loops; fall back to curl when you need a field it does not show.

## Daily activity endpoints

| `--by` | Path | ID filter | Default `page_size` |
|---|---|---|---|
| overall, user | `/user/daily/activity` | `user_id` (one id) | 50, max 1000 |
| team | `/team/daily/activity` | `team_ids` (comma list) | 10 |
| org (Enterprise) | `/organization/daily/activity` | `organization_ids` | 10 |
| tag | `/tag/daily/activity` | `tags` | 10 |
| customer | `/customer/daily/activity` | `end_user_ids` | 10 |
| agent | `/agent/daily/activity` | `agent_ids` | 10 |

All take `start_date`, `end_date`, `model`, `api_key` (key hash), `page`,
`page_size`. Team, org, customer and agent also take `exclude_<same>_ids`. The
user endpoints take `timezone` (minutes, JS `getTimezoneOffset` sign) and
`include_current_utc_day=true`, which pulls today's UTC bucket into a range
that ends on the caller's local today.

```bash
# whole proxy, one call, no paging
curl -sS "$LITELLM_BASE_URL/user/daily/activity/aggregated?start_date=2026-09-01&end_date=2026-09-28" \
  -H "Authorization: Bearer $LITELLM_API_KEY"

# two teams with a per-team breakdown (v1.99+, range at most 400 days)
curl -sS "$LITELLM_BASE_URL/team/daily/activity/aggregated?team_ids=<team_id>,<team_id>&start_date=2026-09-01&end_date=2026-09-28" \
  -H "Authorization: Bearer $LITELLM_API_KEY"

# paginated: keep requesting page=2,3,... while metadata.has_more is true
curl -sS "$LITELLM_BASE_URL/organization/daily/activity?organization_ids=<org_id>&start_date=2026-09-01&end_date=2026-09-28&page_size=1000&page=1" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

Response: `{"results": [{"date", "metrics", "breakdown"}], "metadata": {...}}`.
`metrics` holds `spend`, `prompt_tokens`, `completion_tokens`, `total_tokens`,
`api_requests`, `successful_requests`, `failed_requests`, cache and savings
counters. `breakdown` has `models`, `model_groups`, `providers`, `endpoints`,
`api_keys`, `mcp_servers`, `entities`, each `{name: {"metrics", "metadata"}}`;
`api_keys` are hashes with `metadata.key_alias`. Full field list:
`references/endpoints.md`.

Pagination is the part that gets misread, so be exact about it:

- Paginated endpoints page over raw daily rows (date x entity x key x model x
  provider x endpoint), not over days. One busy day can span several pages, so
  merge `results` by `date` across pages before totalling.
- `metadata.total_spend`, `total_api_requests` and the other `total_*` fields
  cover only the current page. Sum the merged days yourself.
- `metadata` has `page`, `total_pages`, `has_more`. There is no `page_size` or
  `total_count` in it. Loop on `has_more`.
- The `/aggregated` variants return every day in one response with
  `has_more: false`, so their `metadata.total_*` are the real totals.
- `/user/daily/activity/aggregated` has no `breakdown.entities`; use the
  paginated user endpoint when you need per-user rows for everyone.

## Scoping

- Unfiltered `/user/daily/activity` is proxy-wide only for `proxy_admin` and
  `proxy_admin_viewer`. Any other key is silently narrowed to its own user, and
  asking for someone else's `user_id` returns 403.
- Team endpoints: non-admins see only teams they belong to (404 otherwise);
  without team admin rights they get only their own keys' rows.
- Org endpoint: non-admins see only orgs where they are `org_admin`.
- `/customer/daily/activity` is admin-only (v1.90+). Tag and agent endpoints
  narrow non-admins to their own keys or permitted agents.

Say which scope the numbers cover when the key is not a proxy admin.

## Cost attribution with tags

Tag requests (`"metadata": {"tags": ["job:nightly-eval"]}` or the
`x-litellm-tags` header) and read them back. `/tag/daily/activity?tags=<tag>`
gives daily spend with model and key breakdowns. Its totals double count across
tags: a request with three tags lands in three rows, and an unfiltered call also
includes automatic `User-Agent:` tags. Report per tag (`--top entities`), not a
sum across tags.

```bash
# spend and request count per tag, largest first (reads spend logs, so it only
# covers what log retention keeps)
curl -sS "$LITELLM_BASE_URL/global/spend/tags?start_date=2026-09-01&end_date=2026-09-28" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
# -> {"spend_per_tag": [{"name": "job:nightly-eval", "spend": 41.2, "log_count": 1830}, ...]}
# add &tags=job:nightly-eval,job:batch-import to restrict
```

For "which jobs cost the most", call it unfiltered and keep names that look
like job labels (`job:`/`job=`), dropping `User-Agent:` entries.

## Top spenders

- Over a date range: rank `breakdown.api_keys` or `breakdown.entities` from
  daily activity (`--top api_keys`, `--by user --top entities`).
- Current budget-period counters: `GET /user/list?sort_by=spend&sort_order=desc&page_size=25`
  and `GET /key/list?sort_by=spend&sort_order=desc&return_full_object=true`.
  These `spend` values reset every `budget_duration`, so they are not
  period totals; say so.
- Inside a team: `GET /team/spend/by_user?team_ids=<team_id>&start_date=...&end_date=...`
  returns `results` of `{team_id, user_id, user_email, spend, total_tokens,
  api_requests, failed_requests}` sorted by spend (v1.101+, 400-day cap).

## Request logs

```bash
curl -sS "$LITELLM_BASE_URL/spend/logs/v2?start_date=2026-09-27%2000:00:00&end_date=2026-09-27%2023:59:59&status_filter=failure&sort_by=spend&page_size=50" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

Returns `data`, `total`, `page`, `page_size`, `total_pages`. A date-only
`end_date` means midnight at the start of that day, so pass `23:59:59` to
include it. Filters include `key_alias`, `team_id`, `user_id`, `end_user`,
`model`, `model_group`, `error_code`, `min_spend`, `max_spend`, `session_id`;
see `references/endpoints.md`. `/spend/logs` (v1) is deprecated and unpaginated.

## Enterprise spend reports

`GET /key/spend/report`, `/user/spend/report`, `/team/spend/report`,
`/organization/spend/report` (v1.97+) take `start_date`, `end_date` (at most
366 days) and one id param (`api_key`, `internal_user_id`, `team_id`,
`organization_id`); non-admins are pinned to their own identity. Rows are per
key with `total_cost`, token totals and `model_details`.
`/global/spend/report?group_by=team|customer|api_key` is the admin-wide form.
Without an Enterprise license the four scoped reports return 403 and the
global one 400, both saying "You must be a LiteLLM Enterprise user".

## Errors

- **400 "Please provide start_date and end_date"**: add both dates.
- **400 "Date range must be at most 400 days"**: team aggregated and
  `/team/spend/by_user`; split the range or use the paginated endpoint.
- **401 "Admin-only endpoint"**: `/customer/daily/activity` and `/customer/list`
  need a proxy admin or admin viewer key.
- **403 "Organizations are only available for LiteLLM Enterprise users"**:
  org views need a license (v1.102+); report by team instead.
- **403**: another user's `user_id`, a gateway/tool/capture-rate (builds after
  v1.103) view without an admin role, or a spend report scope that is not yours.
- **404 "User does not belong to Team"**: non-admin asked for a team they are
  not in. **404 on `/aggregated`**: proxy predates it; page the plain endpoint.
- **Empty `results`**: no traffic in range, wrong ids, or a scoped key. Daily
  tables are written in batches (every ~10s by default), so the newest
  requests can lag.
- Anything else: show `detail` / `error.message` verbatim.

API reference: https://docs.litellm.ai/docs/proxy/cost_tracking#daily-spend-breakdown-api
