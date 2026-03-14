---
name: add-agent
description: >
  Create a new AI agent on a live LiteLLM proxy. Asks for agent name, the
  underlying model, and optional MCP server access, then calls POST /v1/agents.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Add Agent

Create a new AI agent on a live LiteLLM proxy.

## Setup

Ask for these if not already known:
```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

API reference: https://docs.litellm.ai/docs/proxy/agents

## Ask the user

1. **Agent name** (required, e.g. `my-coding-agent`)
2. **Model** — which LiteLLM model should this agent use (e.g. `gpt-4o`, `claude-3-5-sonnet`)
3. **Description** (optional, shown to callers)
4. **MCP servers** (optional) — list of `server_id`s this agent can use

## Run

```bash
curl -s -X POST "$BASE/v1/agents" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "<name>",
    "litellm_params": {
      "model": "<model>"
    },
    "agent_card_params": {
      "name": "<name>",
      "description": "<description>",
      "version": "1.0"
    }
  }'
```

## List existing agents

```bash
curl -s "$BASE/v1/agents" \
  -H "Authorization: Bearer $KEY"
```

## Get agent info

```bash
curl -s "$BASE/v1/agents/<agent_id>" \
  -H "Authorization: Bearer $KEY"
```

## Delete an agent

```bash
curl -s -X DELETE "$BASE/v1/agents/<agent_id>" \
  -H "Authorization: Bearer $KEY"
```

## Output

Show `agent_id` — needed to call or delete this agent later.
