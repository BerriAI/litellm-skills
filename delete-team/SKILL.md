---
name: delete-team
description: >
  Delete one or more teams from a live LiteLLM proxy. Ask for the team_id(s)
  and confirm before calling POST /team/delete.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Delete Team

Delete one or more teams from a live LiteLLM proxy.

## Setup

```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

## Ask the user

1. **team_id(s)** — if they don't have them, list first:
   ```bash
   curl -s "$BASE/team/list" -H "Authorization: Bearer $KEY"
   ```
2. **Confirm** — show the team alias and ask for confirmation before deleting.

## Run

```bash
curl -s -X POST "$BASE/team/delete" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"team_ids": ["<team_id>"]}'
```

Multiple teams: `"team_ids": ["id1", "id2"]`

## Output

Show the `deleted_teams` list from the response.
