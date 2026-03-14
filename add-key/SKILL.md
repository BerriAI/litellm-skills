---
name: add-key
description: >
  Generate a new API key on a live LiteLLM proxy. Asks for alias, scope
  (user/team), budget, models, and expiry, then calls POST /key/generate.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Add Key

Generate a new API key on a live LiteLLM proxy.

## Setup

Ask for these if not already known:
```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

API reference: https://litellm.vercel.app/docs/proxy/virtual_keys

## Ask the user

1. **Key alias** (optional but recommended, e.g. `my-app-prod`)
2. **Scope** — assign to a `team_id` or `user_id`? (optional)
3. **Allowed models** (optional, e.g. `gpt-4o, claude-3-5-sonnet`)
4. **Max budget** (optional, e.g. `5.00`)
5. **Expiry** (optional, e.g. `7d`, `30d`, `90d`) — omit for no expiry

## Run

```bash
curl -s -X POST "$BASE/key/generate" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key_alias": "<alias>",
    "team_id": "<team_id_or_omit>",
    "user_id": "<user_id_or_omit>",
    "models": [<models_or_empty>],
    "max_budget": <budget_or_null>,
    "duration": "<duration_or_omit>"
  }'
```

## Output

Show the user:
- `key` — the actual key value (only shown once, tell them to save it)
- `key_alias`, `expires`, `max_budget`, `models`

On error show `detail` and the likely fix.
