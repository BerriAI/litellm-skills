---
name: add-key
description: "Generate a new API key on a live LiteLLM proxy. Asks for alias, scope (user/team), budget, models, and expiry, then calls POST /key/generate. Use when the user wants to create, generate, or provision an API key on a LiteLLM proxy instance."
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
BASE="$LITELLM_BASE_URL"
KEY="$LITELLM_API_KEY"

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

## Verify

Confirm the key was created:
```bash
curl -s "$BASE/key/info" \
  -H "Authorization: Bearer <new_key>" | python3 -c "
import sys, json
d = json.load(sys.stdin)
info = d.get('info', {})
print(f'Alias: {info.get(\"key_alias\")}')
print(f'Expires: {info.get(\"expires\")}')
print(f'Budget: {info.get(\"max_budget\")}')
print(f'Models: {info.get(\"models\")}')
"
```

## Output

Show the user:
- `key` — the actual key value (only shown once, tell them to save it)
- `key_alias`, `expires`, `max_budget`, `models`

On error:
- **401** — check that `LITELLM_API_KEY` is a valid admin key
- **400** — check required fields; verify `team_id`/`user_id` exists
- Other errors — show `detail` and the likely fix
