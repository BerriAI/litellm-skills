---
name: add-user
description: >
  Create a new user on a live LiteLLM proxy. Asks for email, role, and optional
  budget/model limits, then calls POST /user/new and shows the result.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Add User

Create a new user on a live LiteLLM proxy.

## Setup

Ask for these if not already known:
```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

API reference: https://litellm.vercel.app/docs/proxy/virtual_keys#creating-a-user

## Ask the user

1. **Email** (required)
2. **Role** — one of: `proxy_admin`, `proxy_admin_viewer`, `internal_user` (default), `internal_user_viewer`
3. **Max budget** (optional, e.g. `10.00`)
4. **Allowed models** (optional, e.g. `gpt-4o, claude-3-5-sonnet`)

## Run

```bash
curl -s -X POST "$BASE/user/new" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_email": "<email>",
    "user_role": "<role>",
    "max_budget": <budget_or_null>,
    "models": [<models_or_empty>]
  }'
```

## Output

Show the user:
- `user_id` — they'll need this for future updates
- `key` — the auto-generated API key for this user
- `user_role`, `max_budget`

On error show `detail` and the likely fix.
