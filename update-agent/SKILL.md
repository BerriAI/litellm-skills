---
name: update-agent
description: >
  Update an existing AI agent on a live LiteLLM proxy. Ask for the agent_id
  and what to change (model, description, MCP servers), then call PATCH /v1/agents/{agent_id}.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Update Agent

Update an existing AI agent on a live LiteLLM proxy.

## Setup

```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

## Ask the user

1. **agent_id** — if they don't have it, list first:
   ```bash
   curl -s "$BASE/v1/agents" -H "Authorization: Bearer $KEY"
   ```
2. **What to change** — any combination of:
   - `model` (swap the underlying model)
   - `description`
   - `tpm_limit` / `rpm_limit`
   - MCP server access

## Run

Use PATCH to update only the changed fields:

```bash
curl -s -X PATCH "$BASE/v1/agents/<agent_id>" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "litellm_params": {"model": "<new_model>"},
    "agent_card_params": {"description": "<new_description>"}
  }'
```

## Output

Show the updated agent name, model, and description. Confirm the agent ID is unchanged.
