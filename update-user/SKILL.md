---
name: update-user
description: >
  Update an existing user on a live LiteLLM proxy. Ask for the user_id and
  what to change (budget, role, models, etc.), then call POST /user/update.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Update User

Update an existing user on a live LiteLLM proxy.

## Setup

```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

API reference: https://litellm.vercel.app/docs/proxy/virtual_keys#updating-a-user

## Ask the user

1. **user_id** (required) — if they don't have it, list users first:
   ```bash
   curl -s "$BASE/user/list?page_size=25" -H "Authorization: Bearer $KEY"
   ```
2. **What to change** — any combination of:
   - `max_budget` (float)
   - `user_role` (`proxy_admin`, `proxy_admin_viewer`, `internal_user`, `internal_user_viewer`)
   - `models` (list)
   - `tpm_limit` / `rpm_limit` (int)
   - `user_email`, `user_alias`

## Run

```bash
curl -s -X POST "$BASE/user/update" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<user_id>",
    "max_budget": <value>,
    "user_role": "<role>",
    "models": [<models>]
  }'
```

Only include the fields being changed.

## Output

Show the updated `user_id`, `max_budget`, `user_role`, `models`.
