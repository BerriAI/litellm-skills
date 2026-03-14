---
name: update-model
description: >
  Update an existing model on a live LiteLLM proxy. Ask for the model_id and
  what to change (API key, base URL, etc.), then call POST /model/update.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Update Model

Update an existing model's configuration on a live LiteLLM proxy.

## Setup

```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

## Ask the user

1. **model_id** (required) — if they don't have it, list models first:
   ```bash
   curl -s "$BASE/model/info" -H "Authorization: Bearer $KEY" | python3 -c "
   import sys,json
   for m in json.load(sys.stdin).get('data',[]):
     print(m['model_info']['id'], m['model_name'])
   "
   ```
2. **What to change** — any combination of:
   - `api_key` (rotate the credential)
   - `api_base` (change endpoint)
   - `api_version` (Azure)
   - `model` (underlying model string, e.g. `azure/new-deployment`)

## Run

```bash
curl -s -X POST "$BASE/model/update" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model_info": {"id": "<model_id>"},
    "litellm_params": {
      "api_key": "<new_key>",
      "api_base": "<new_base>"
    }
  }'
```

Only include `litellm_params` fields being changed.

## Output

Confirm the model was updated. Offer to run a test call to verify it still routes correctly.
