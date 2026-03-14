---
name: update-key
description: >
  Update an existing API key on a live LiteLLM proxy. Ask for the key and
  what to change (budget, models, expiry), then call POST /key/update.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Update Key

Update an existing API key on a live LiteLLM proxy.

## Setup

```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

API reference: https://litellm.vercel.app/docs/proxy/virtual_keys

## Ask the user

1. **Key** (required) — the `sk-...` value. If they don't have it, list keys:
   ```bash
   curl -s "$BASE/key/list?size=25&return_full_object=true" -H "Authorization: Bearer $KEY"
   ```
2. **What to change** — any combination of:
   - `max_budget` (float)
   - `models` (list)
   - `key_alias` (string)
   - `tpm_limit` / `rpm_limit` (int)
   - `duration` (e.g. `30d` — extends expiry from now)
   - `team_id` / `user_id` (reassign ownership)

## Run

```bash
curl -s -X POST "$BASE/key/update" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "<sk-...>",
    "max_budget": <value>,
    "models": [<models>],
    "duration": "<duration>"
  }'
```

Only include the fields being changed.

## Output

Show the updated `key_alias`, `max_budget`, `models`, `expires`.
