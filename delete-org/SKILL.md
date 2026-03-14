---
name: delete-org
description: >
  Delete one or more organizations from a live LiteLLM proxy. Ask for the
  organization_id(s) and confirm before calling DELETE /organization/delete.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Delete Organization

Delete one or more organizations from a live LiteLLM proxy.

## Setup

```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

## Ask the user

1. **organization_id(s)** — if they don't have them, list first:
   ```bash
   curl -s "$BASE/organization/list" -H "Authorization: Bearer $KEY"
   ```
2. **Confirm** — show the org alias and ask for confirmation before deleting.

## Run

```bash
curl -s -X DELETE "$BASE/organization/delete" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"organization_ids": ["<org_id>"]}'
```

## Output

Show the deleted org ID(s) and alias(es) from the response.
