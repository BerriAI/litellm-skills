---
name: update-team
description: >
  Update an existing team on a live LiteLLM proxy. Ask for the team_id and
  what to change (budget, models, limits), then call POST /team/update.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Update Team

Update an existing team on a live LiteLLM proxy.

## Setup

```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

API reference: https://litellm.vercel.app/docs/proxy/team_based_routing

## Ask the user

1. **team_id** (required) — if they don't have it, list teams first:
   ```bash
   curl -s "$BASE/team/list" -H "Authorization: Bearer $KEY"
   ```
2. **What to change** — any combination of:
   - `team_alias` (string)
   - `max_budget` (float)
   - `models` (list)
   - `tpm_limit` / `rpm_limit` (int)
   - `blocked` (bool — blocks all requests from this team)

## Run

```bash
curl -s -X POST "$BASE/team/update" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "<team_id>",
    "max_budget": <value>,
    "models": [<models>],
    "tpm_limit": <value>
  }'
```

Only include the fields being changed.

## Output

Show the updated `team_id`, `team_alias`, `max_budget`, `models`.
