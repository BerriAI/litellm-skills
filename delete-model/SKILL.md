---
name: delete-model
description: >
  Delete a model from a live LiteLLM proxy. Ask for the model name or model_id
  and confirm before calling POST /model/delete.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Delete Model

Remove a model from a live LiteLLM proxy.

## Setup

```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

## Ask the user

1. **Model name or model_id** — if they give a name, look up the ID first:
   ```bash
   curl -s "$BASE/model/info" -H "Authorization: Bearer $KEY" | python3 -c "
   import sys,json
   for m in json.load(sys.stdin).get('data',[]):
     print(m['model_info']['id'], m['model_name'])
   "
   ```
2. **Confirm** — show the model name and ask for confirmation before deleting.

## Run

```bash
curl -s -X POST "$BASE/model/delete" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"id": "<model_id>"}'
```

## Output

Show the success message. Warn the user that any keys scoped to this model name will start getting errors.
