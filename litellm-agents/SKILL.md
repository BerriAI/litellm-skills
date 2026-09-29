---
name: litellm-agents
description: >
  Register, test, update, and remove A2A agents on a live LiteLLM proxy (AI
  gateway) with curl, and control who can call them. Use this whenever someone
  wants to put an agent behind LiteLLM (an A2A server, LangGraph, Bedrock
  AgentCore, Pydantic AI, LangFlow, watsonx Orchestrate, Azure AI Foundry);
  fetch an agent's card before registering it; send a test message to an
  agent; change an agent's URL, card, rate limits, or MCP tool access; find
  agents by what they do; give a key or team access to an agent; set up or fire
  an agent's kill switch; or delete an agent. Also use it when a user mentions
  "agent gateway", "a2a/<name>" models, an "Agent has no URL configured" error,
  or asks why a key cannot reach an agent.
license: MIT
compatibility: Requires curl and python3. Written against LiteLLM v1.103 (September 2026).
metadata:
  author: BerriAI
  version: "2.0"
allowed-tools: Bash(curl:*) Bash(python3:*)
---

# LiteLLM agents

A LiteLLM agent is a registry entry that fronts a backend agent. Clients call
the proxy over A2A (or `/chat/completions` with `model: "a2a/<agent_name>"`);
LiteLLM checks access, applies rate limits and guardrails, logs spend, and
forwards to the backend named in `agent_card_params.url`.

## Connect

Read `LITELLM_BASE_URL` and `LITELLM_API_KEY` from the environment. If either is
missing, ask for it once and export it for the rest of the session. Creating,
updating, deleting, discovering, and firing kill switches needs a proxy admin
key; any key can list and call the agents it has been granted. Never echo the
admin key or an agent's backend credentials back into logs you don't need to.

```bash
curl -sS "$LITELLM_BASE_URL/health/readiness/details" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

Skip it if you already checked this proxy earlier in the session. It confirms
the URL and key work and returns `litellm_version`. Features
below that changed recently name the version they arrived in; if the proxy is
older, say so instead of guessing.

Append `-w '\nHTTP %{http_code}\n'` to write calls so the status is visible.

## Pick the operation

| The user wants to | Call |
|---|---|
| Read a backend's agent card first | `POST /v1/a2a/discover` |
| Register an agent | `POST /v1/agents` |
| List, health-filter, or search | `GET /v1/agents` (`?health_check=true`, `?query=&top_k=` v1.100+) |
| Inspect one | `GET /v1/agents/{agent_id}` |
| Send a test message | `POST /a2a/{agent_id}` (JSON-RPC) or `POST /v1/chat/completions` |
| Change fields | `PATCH /v1/agents/{agent_id}` (or `PUT` for a full replace) |
| Give a key or team access | `POST /key/update`, `POST /team/update` with `object_permission.agents` |
| Fire the kill switch (builds after v1.103) | `POST /v1/agents/{agent_id}/kill_switch` |
| Remove an agent | `DELETE /v1/agents/{agent_id}` |

`{agent_id}` on the `/a2a/...` routes also accepts the `agent_name`; the
`/v1/agents/...` management routes need the id.

## Register an agent

1. Optionally fetch the backend's card so name, description, and skills come
   from the source. LiteLLM tries `/.well-known/agent-card.json`,
   `/.well-known/agent.json`, then `/agent.json` under the URL (use
   `"discovery_mode": "langgraph_platform"` with `"params": {"assistant_id": "..."}`
   for LangGraph Platform):

```bash
curl -sS -X POST "$LITELLM_BASE_URL/v1/a2a/discover" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"url": "https://research-agent.internal.example.com"}'
```

2. Collect `agent_name` (unique; it is what `a2a/<agent_name>` resolves) and
   `agent_card_params`, which is required and must carry `url`, the backend's
   A2A endpoint, unless you use a completion bridge (below). Pin
   `protocolVersion` to `"1.0"` or `"0.3"` so the card and responses match what
   the client expects; anything else is a 400.
3. Optional: `tpm_limit`, `rpm_limit`, per-session limits, `static_headers`,
   and `object_permission` for the agent's own MCP and model access. See
   `references/fields.md`.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/v1/agents" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{
    "agent_name": "research-agent",
    "agent_card_params": {
      "protocolVersion": "1.0",
      "name": "Research Agent",
      "description": "Answers questions from internal research docs",
      "url": "https://research-agent.internal.example.com/",
      "capabilities": {"streaming": true},
      "skills": [{"id": "doc_qa", "name": "Document Q&A",
                  "description": "Answer questions about internal docs", "tags": ["research"]}]
    },
    "rpm_limit": 60,
    "object_permission": {"mcp_servers": ["github_mcp"]}
  }'
```

Show `agent_id`, `agent_name`, and `agent_card_params.url`. LiteLLM rewrites the
card on save: it fills missing `version`, `skills`, and input/output modes,
replaces `securitySchemes`/`security` with its own (callers authenticate with a
LiteLLM key), and adds `supportedInterfaces` pointing at `/a2a/{agent_id}`. The
stored `url` stays the backend; the card served to clients shows the proxy URL.

**Completion bridge.** For backends that are not A2A servers (LangGraph,
Bedrock AgentCore, Pydantic AI, LangFlow, watsonx Orchestrate, or any LiteLLM
provider), set `litellm_params.custom_llm_provider` (and `model` where needed);
LiteLLM translates A2A into a completion call with the card `url` as
`api_base`. Examples are in `references/fields.md`. `litellm_params.model`
without `custom_llm_provider` does nothing, and an agent with neither `url` nor
a provider fails every call with "Agent has no URL configured". Bridge-only
agents support `message/send` and `message/stream`, not task methods.

## Test an agent

Call it with a key that has access (the admin key works) and show the reply.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/a2a/research-agent" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": "1", "method": "message/send",
       "params": {"message": {"role": "user", "messageId": "msg-001",
                  "parts": [{"kind": "text", "text": "What can you do?"}]}}}'

curl -sS -X POST "$LITELLM_BASE_URL/v1/chat/completions" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"model": "a2a/research-agent", "messages": [{"role": "user", "content": "What can you do?"}]}'

curl -sS "$LITELLM_BASE_URL/a2a/research-agent/.well-known/agent-card.json" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

`/v1/a2a/{agent_id}/message/send` is an alias. Errors come back as JSON-RPC
`error` objects (for example code -32000 "not found"), so read the body, not
only the status. If the agent sets
`litellm_params.require_trace_id_on_calls_to_agent`, add `x-litellm-trace-id`.

## List and search

`GET /v1/agents` returns the agents the calling key can reach, with `spend`
and, for admins, bound `keys`. `?health_check=true` drops agents whose backend
URL fails or returns 5xx. `?query=translate+a+PDF&top_k=5` (v1.100+) ranks by
semantic match with a `search_score`; it needs
`litellm_settings.agent_search_embedding_model`.

## Update an agent

GET the agent first. `PATCH /v1/agents/{agent_id}` changes only the top-level
fields you send, but `agent_card_params` and `litellm_params` are each replaced
as a whole: a PATCH with `{"agent_card_params": {"description": "..."}}` drops
the stored `url`, name, and skills, and the agent stops working. So modify the
fetched object and send the complete `agent_card_params` or `litellm_params`.
Secrets in `litellm_params` come back as `REDACTED_BY_LITELM`; sending that
marker (or omitting a secret key) keeps the stored value.

```bash
curl -sS "$LITELLM_BASE_URL/v1/agents/<agent_id>" -H "Authorization: Bearer $LITELLM_API_KEY" > agent.json
python3 - <<'EOF' > patch.json
import json
a = json.load(open("agent.json"))
card = a["agent_card_params"]
card["url"] = "https://research-agent-v2.internal.example.com/"
print(json.dumps({"agent_card_params": card, "rpm_limit": 120}))
EOF
curl -sS -X PATCH "$LITELLM_BASE_URL/v1/agents/<agent_id>" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' -d @patch.json
```

`tpm_limit`, `rpm_limit`, `session_tpm_limit`, `session_rpm_limit`,
`static_headers`, and `extra_headers` (plus `kill_switch` on builds after
v1.103) are top level; `null` clears them on PATCH. `object_permission` merges per field (a sent
`mcp_servers` list replaces the stored one; unsent fields stay). `PUT` needs
`agent_name` and `agent_card_params` and resets omitted `static_headers` and
`extra_headers` (and `access_group_ids` and `kill_switch` on builds after
v1.103), so prefer PATCH.

## Access

Keys and teams reach agents through `object_permission.agents` (agent ids) or
`object_permission.agent_access_groups`; a key's grants intersect with its
team's. Read the current list with `GET /key/info` and send the union, since a
sent list replaces the stored one:

```bash
curl -sS -X POST "$LITELLM_BASE_URL/key/update" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"key_alias": "support-portal-prod", "object_permission": {"agents": ["<agent_id>"]}}'
```

A key created with `"agent_id": "<agent_id>"` on `/key/generate` is the agent's
own identity for its outbound LLM and MCP calls; the `litellm-keys` skill
covers the rest of the key.

## Kill switch (builds after v1.103)

v1.103 has no kill switch: the route returns 404 and a `kill_switch` field is
not stored. Treat a 404 as "proxy too old" and cut the agent off the v1.103
way instead, by deleting it or removing its `object_permission.agents` grants
from keys and teams. On builds after v1.103, `kill_switch` stores a webhook (`url`, `method`, `headers`, `query_params`,
`body`, `auth`) that stops the agent's runtime. Set it with PATCH, then fire:

```bash
curl -sS -X POST "$LITELLM_BASE_URL/v1/agents/<agent_id>/kill_switch" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -w '\nHTTP %{http_code}\n'
```

Confirm before firing. It only calls the webhook: the agent stays registered
and callable in LiteLLM, so delete it or revoke grants separately if needed.
200 means the webhook answered 2xx, 502 carries the failed result, 400 means
none is configured.

## Delete an agent

GET the agent, show `agent_name`, `agent_card_params.url`, `spend`, and its
`keys`, and get an explicit yes. Deletion is immediate and not reversible.
Keys bound to it via `agent_id` and `object_permission.agents` grants on keys
and teams are left pointing at a missing id; offer to revoke or update them.

```bash
curl -sS -X DELETE "$LITELLM_BASE_URL/v1/agents/<agent_id>" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -w '\nHTTP %{http_code}\n'
```

Returns 200 with `{"message": "Agent <id> deleted successfully"}`; 404 if the
id is unknown or the agent is defined in `config.yaml` (edit the file instead).

## Errors

- **400 "Agent with name ... already exists"**: names are unique; PATCH the
  existing one or pick another.
- **400 "Unsupported protocolVersion"**: only `0.3` and `1.0` (with semver
  forms like `0.3.0`).
- **422 missing `agent_card_params`**: it is required even for bridge agents.
- **403 "Only proxy admins can create, update, or delete agents"** or "not
  allowed for your key/team": use an admin key, or grant the agent to the key.
- **JSON-RPC -32000 "has no URL configured"**: set `agent_card_params.url` or a
  `custom_llm_provider`.
- **400 "requires x-litellm-trace-id"**: the agent enforces a trace header.
- **400 `agent_search_not_configured`**: set `agent_search_embedding_model`.
- Anything else: show `detail` / `error` verbatim and the likely fix. Docs:
  https://docs.litellm.ai/docs/a2a and https://docs.litellm.ai/docs/a2a_agent_permissions
