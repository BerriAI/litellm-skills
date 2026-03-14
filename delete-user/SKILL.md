---
name: delete-user
description: >
  Delete one or more users from a live LiteLLM proxy. Ask for the user_id(s)
  and confirm before calling POST /user/delete.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Delete User

Delete one or more users from a live LiteLLM proxy.

## Setup

```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

## Ask the user

1. **user_id(s)** — if they don't have them, list first:
   ```bash
   curl -s "$BASE/user/list?page_size=25" -H "Authorization: Bearer $KEY"
   ```
2. **Confirm** — show the user email/alias and ask for confirmation before deleting.

## Run

```bash
curl -s -X POST "$BASE/user/delete" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_ids": ["<user_id>"]}'
```

Multiple users: `"user_ids": ["id1", "id2"]`

## Output

Show how many users were deleted. Warn if any IDs were not found.
