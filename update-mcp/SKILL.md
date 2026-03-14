---
name: update-mcp
description: >
  Update an existing MCP server on a live LiteLLM proxy. Ask for the server_id
  and what to change (URL, auth, description), then call PUT /v1/mcp/server.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Update MCP Server

Update an existing MCP server registration on a live LiteLLM proxy.

## Setup

```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

## Ask the user

1. **server_id** — if they don't have it, list first:
   ```bash
   curl -s "$BASE/v1/mcp/server" -H "Authorization: Bearer $KEY"
   ```
2. **What to change** — any combination of:
   - `url`
   - `credentials` (rotate the auth token)
   - `description`
   - `allowed_tools` (list of tool names to expose)

## Run

```bash
curl -s -X PUT "$BASE/v1/mcp/server" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "server_id": "<server_id>",
    "url": "<new_url>",
    "credentials": "<new_token>"
  }'
```

Only include the fields being changed.

## Output

Confirm the server was updated and show the updated fields.
