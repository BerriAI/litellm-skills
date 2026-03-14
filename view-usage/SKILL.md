---
name: view-usage
description: >
  Query spend and activity on a live LiteLLM proxy. Shows daily token usage,
  cost, request counts broken down by user, team, org, model, or API key.
  Use when the user wants to see how much has been spent, who is using what,
  or which models are being called most.
license: MIT
compatibility: Requires curl. Proxy must be running and reachable.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# View Usage

Query daily activity and spend data from a live LiteLLM proxy.

## Setup

Ask for these if not already available:
```
LITELLM_BASE_URL  — e.g. http://localhost:4000
LITELLM_API_KEY   — admin/master key
```

```bash
BASE="<LITELLM_BASE_URL>"
KEY="<LITELLM_API_KEY>"
```

API reference: https://litellm.vercel.app/docs/proxy/users#get-user-spend

---

## Activity endpoints

All endpoints accept the same query parameters:

| Param | Description | Example |
|---|---|---|
| `start_date` | From date (inclusive) | `2025-01-01` |
| `end_date` | To date (inclusive) | `2025-01-31` |
| `model` | Filter by model name | `gpt-4o` |
| `api_key` | Filter by API key hash | |
| `page` | Page number (default 1) | `1` |
| `page_size` | Results per page (default 10–50) | `25` |

### Overall daily activity (across all users)
```bash
curl -s "$BASE/user/daily/activity?start_date=2025-01-01&end_date=2025-01-31&page_size=30" \
  -H "Authorization: Bearer $KEY" | python3 -m json.tool
```

### By user
```bash
curl -s "$BASE/user/daily/activity?user_id=<user_id>&start_date=2025-01-01&end_date=2025-01-31" \
  -H "Authorization: Bearer $KEY" | python3 -m json.tool
```

### By team
```bash
curl -s "$BASE/team/daily/activity?team_ids=<team_id>&start_date=2025-01-01&end_date=2025-01-31" \
  -H "Authorization: Bearer $KEY" | python3 -m json.tool
```

### By organization
```bash
curl -s "$BASE/organization/daily/activity?organization_ids=<org_id>&start_date=2025-01-01&end_date=2025-01-31" \
  -H "Authorization: Bearer $KEY" | python3 -m json.tool
```

### By tag
```bash
curl -s "$BASE/tag/daily/activity?start_date=2025-01-01&end_date=2025-01-31" \
  -H "Authorization: Bearer $KEY" | python3 -m json.tool
```

---

## Response shape

```json
{
  "data": [
    {
      "date": "2025-01-15",
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
        "models": {
          "gpt-4o": { "spend": 0.90, "total_tokens": 40000 },
          "gpt-4o-mini": { "spend": 0.33, "total_tokens": 17000 }
        },
        "providers": {
          "openai": { "spend": 1.23 }
        }
      }
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_count": 31,
    "total_pages": 4
  }
}
```

---

## Total spend for a key or user

### Key spend
```bash
curl -s "$BASE/key/info?key=<the-key>" \
  -H "Authorization: Bearer $KEY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
info = d.get('info', d)
print(f'Key:      {info.get(\"key_alias\", \"(no alias)\")}')
print(f'Spend:    \${info.get(\"spend\", 0):.4f}')
print(f'Budget:   \${info.get(\"max_budget\", \"unlimited\")}')
"
```

### User spend
```bash
curl -s "$BASE/user/info?user_id=<user_id>" \
  -H "Authorization: Bearer $KEY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
u = d.get('user_info', d)
print(f'User:   {u.get(\"user_email\", u.get(\"user_id\"))}')
print(f'Spend:  \${u.get(\"spend\", 0):.4f}')
print(f'Budget: \${u.get(\"max_budget\", \"unlimited\")}')
"
```

---

## Aggregated summary (no pagination)

For a single rolled-up row across a date range:
```bash
curl -s "$BASE/user/daily/activity/aggregated?start_date=2025-01-01&end_date=2025-01-31" \
  -H "Authorization: Bearer $KEY" | python3 -m json.tool
```

---

## Instructions

1. Ask the user what they want to see: overall / by user / by team / by org / by tag.
2. Ask for the date range. Default to the current month if not specified (use today's date to compute `start_date` and `end_date`).
3. Ask if they want to filter by a specific model or API key (optional).
4. Run the appropriate curl and summarize the response as a human-readable table:
   - Columns: Date, Requests, Tokens (prompt / completion), Spend ($)
   - Footer: totals row
5. If the response spans multiple pages, offer to fetch the next page.
6. Highlight any days with failed requests > 0.
