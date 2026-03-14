---
name: delete-mcp
description: >
  Delete an MCP server from a live LiteLLM proxy. Ask for the server_id and
  confirm before calling DELETE /v1/mcp/server/{server_id}.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Delete MCP Server

Remove an MCP server registration from a live LiteLLM proxy.

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
2. **Confirm** — show the server name/URL and ask for confirmation.

## Run

```bash
curl -s -X DELETE "$BASE/v1/mcp/server/<server_id>" \
  -H "Authorization: Bearer $KEY"
```

## Output

Confirm deletion. Note that any agents using this MCP server will lose access to its tools.
