---
name: add-mcp
description: >
  Register a new MCP server on a live LiteLLM proxy. Asks for the server name,
  transport type, URL, and optional auth, then calls POST /v1/mcp/server.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Add MCP Server

Register an MCP (Model Context Protocol) server on a live LiteLLM proxy so it can be used by models and agents.

## Setup

Ask for these if not already known:
```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

API reference: https://docs.litellm.ai/docs/mcp

## Ask the user

1. **Server name** (required, e.g. `my-github-mcp`)
2. **URL** (required, e.g. `https://mcp.example.com/sse`)
3. **Transport** — `sse` (default), `http`, or `stdio`
4. **Description** (optional)
5. **Auth** — does it need a bearer token or API key? (optional)

## Run

```bash
curl -s -X POST "$BASE/v1/mcp/server" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "<name>",
    "url": "<url>",
    "transport": "sse",
    "description": "<description_or_omit>",
    "auth_type": "bearer_token",
    "credentials": "<token_if_needed>"
  }'
```

For unauthenticated servers, omit `auth_type` and `credentials`.

## List existing MCP servers

```bash
curl -s "$BASE/v1/mcp/server" \
  -H "Authorization: Bearer $KEY"
```

## Delete an MCP server

```bash
curl -s -X DELETE "$BASE/v1/mcp/server/<server_id>" \
  -H "Authorization: Bearer $KEY"
```

## Output

Show `server_id` — needed to reference this MCP server in agent configs or to delete it later.
