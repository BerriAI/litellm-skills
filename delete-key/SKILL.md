---
name: delete-key
description: >
  Delete one or more API keys from a live LiteLLM proxy. Ask for the key(s)
  and confirm before calling POST /key/delete.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Delete Key

Delete one or more API keys from a live LiteLLM proxy.

## Setup

```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

## Ask the user

1. **Key(s)** (`sk-...`) or **key alias(es)** — if they don't have them, list first:
   ```bash
   curl -s "$BASE/key/list?size=25&return_full_object=true" -H "Authorization: Bearer $KEY"
   ```
2. **Confirm** — show the key alias and ask for confirmation before deleting.

## Run

By key value:
```bash
curl -s -X POST "$BASE/key/delete" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"keys": ["<sk-...>"]}'
```

By alias:
```bash
curl -s -X POST "$BASE/key/delete" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"key_aliases": ["<alias>"]}'
```

## Output

Show the `deleted_keys` list from the response.
