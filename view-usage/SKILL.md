---
name: view-usage
description: >
  Query spend and token activity on a live LiteLLM proxy. Shows daily usage
  broken down by user, team, org, or model. Use when the user wants to see
  costs, token counts, or request volume for a given date range.
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

API reference: https://litellm.vercel.app/docs/proxy/users#get-user-spend

## Ask the user

1. **View by** — overall / user / team / org / tag (default: overall)
2. **Date range** — default to current month if not given
3. **Filter by model?** (optional)

## Endpoints

### Overall (across all users)
```bash
curl -s "$BASE/user/daily/activity?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&page_size=30" \
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

### By tag
```bash
curl -s "$BASE/tag/daily/activity?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD" \
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
print(f'{'Date':<12} {'Requests':>10} {'Tokens':>12} {'Spend':>10}')
print('-' * 46)
total_spend = 0
for r in rows:
    m = r.get('metrics', {})
    print(f'{r[\"date\"]:<12} {m.get(\"api_requests\",0):>10} {m.get(\"total_tokens\",0):>12} \${m.get(\"spend\",0):>9.4f}')
    total_spend += m.get('spend', 0)
print('-' * 46)
print(f'{'TOTAL':<12} {'':>10} {'':>12} \${total_spend:>9.4f}')
"
```

## Instructions

1. Ask for date range — default to current month.
2. Run the appropriate endpoint.
3. Print a table: Date | Requests | Tokens | Spend.
4. Show totals row at the bottom.
5. Highlight any days with `failed_requests > 0`.
6. If `metadata.total_pages > 1`, offer to fetch remaining pages.
