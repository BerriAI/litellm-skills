---
name: view-usage
description: >
  Query spend and token activity on a live LiteLLM proxy. Shows daily usage
  broken down by user, team, org, tag, job, or model. Use when the user wants
  to see costs, token counts, request volume, or job-level attribution for a
  given date range.
license: MIT
compatibility: Requires curl and python3.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*) Bash(python3:*)
---

# View Usage

Query daily activity and spend data from a live LiteLLM proxy.

## Setup

Ask for these if not already known:
```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

API reference: https://docs.litellm.ai/docs/proxy/users#get-user-spend

## Ask the user

1. **View by** — overall / user / team / org / tag / job (default: overall)
2. **Date range** — default to current month if not given
3. **Filter by model?** (optional)
4. **Job tag(s)?** (optional) — for job cost attribution, ask which request
   tag identifies the job, for example `job:nightly-eval` or `job=batch-import`.

## Job cost attribution

LiteLLM attributes per-request costs through request tags. For LLM jobs, prefer
tagging requests with a stable job label such as `job:<job-name>` and then query
tag APIs:

- Use `/tag/daily/activity?tags=<tag>` for daily spend, tokens, request count,
  and model/provider breakdowns for one or more job tags.
- Use `/global/spend/tags?tags=<tag>` for a top-level spend total by tag over a
  date range.
- If the user asks "which jobs cost the most?", call `/global/spend/tags`
  without a `tags` filter, sort by spend descending, and present the top tags
  that look like job labels.

## Endpoints

### Overall spend (across all users)
```bash
curl -s "$BASE/user/daily/activity?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&page_size=30" \
  -H "Authorization: Bearer $KEY"
```

### Overall request and token volume
```bash
curl -s "$BASE/global/activity?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD" \
  -H "Authorization: Bearer $KEY"
```

### By team
```bash
curl -s "$BASE/team/daily/activity?team_ids=<team_id>&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD" \
  -H "Authorization: Bearer $KEY"
```

### By org
```bash
curl -s "$BASE/organization/daily/activity?organization_ids=<org_id>&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD" \
  -H "Authorization: Bearer $KEY"
```

### By user
```bash
curl -s "$BASE/user/daily/activity?user_id=<user_id>&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD" \
  -H "Authorization: Bearer $KEY"
```

### By tag or job
```bash
curl -s "$BASE/tag/daily/activity?tags=<tag>&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&page_size=30" \
  -H "Authorization: Bearer $KEY"
```

For multiple tags, pass a comma-separated list:
```bash
curl -s "$BASE/tag/daily/activity?tags=job:nightly-eval,job:batch-import&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&page_size=30" \
  -H "Authorization: Bearer $KEY"
```

### Top tag spend
```bash
curl -s "$BASE/global/spend/tags?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD" \
  -H "Authorization: Bearer $KEY"
```

Filter to a specific job tag:
```bash
curl -s "$BASE/global/spend/tags?tags=<tag>&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD" \
  -H "Authorization: Bearer $KEY"
```

## Response shape

```json
{
  "results": [
    {
      "date": "2026-03-14",
      "metrics": {
        "spend": 1.23,
        "prompt_tokens": 45000,
        "completion_tokens": 12000,
        "total_tokens": 57000,
        "api_requests": 120,
        "successful_requests": 118,
        "failed_requests": 2
      },
      "breakdown": {
        "models": { "gpt-4o": { "metrics": { "spend": 1.23, ... } } }
      }
    }
  ],
  "metadata": { "page": 1, "page_size": 10, "total_count": 31 }
}
```

Note: top-level key is `results` (not `data`).

## Summarize with python3

```bash
curl -s "$BASE/user/daily/activity?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&page_size=30" \
  -H "Authorization: Bearer $KEY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
rows = d.get('results', [])
print('{:<12} {:>10} {:>12} {:>10}'.format('Date', 'Requests', 'Tokens', 'Spend'))
print('-' * 46)
total_spend = 0
for r in rows:
    m = r.get('metrics', {})
    print('{:<12} {:>10} {:>12} ${:>9.4f}'.format(
        r.get('date', ''),
        m.get('api_requests', 0),
        m.get('total_tokens', 0),
        m.get('spend', 0),
    ))
    total_spend += m.get('spend', 0)
print('-' * 46)
print('{:<12} {:>10} {:>12} ${:>9.4f}'.format('TOTAL', '', '', total_spend))
"
```

## Error handling

Before processing results, check the HTTP status:
- **401/403** — invalid or expired `LITELLM_API_KEY`; ask the user to verify
- **404** — endpoint not available; check LiteLLM proxy version supports activity endpoints
- **Empty results** — no activity in the given date range; confirm dates are correct

## Instructions

1. Ask for date range — default to current month.
2. Run the appropriate endpoint. For job attribution, prefer tag endpoints and
   ask for the job tag if it was not provided.
3. Print a table: Date | Requests | Tokens | Spend.
4. Show totals row at the bottom.
5. Highlight any days with `failed_requests > 0`.
6. If `metadata.total_pages > 1`, offer to fetch remaining pages.
