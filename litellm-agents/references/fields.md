# Agent fields

Fields accepted by `POST /v1/agents`, `PATCH /v1/agents/{agent_id}`, and
`PUT /v1/agents/{agent_id}` (LiteLLM v1.103). Send only what the user asked for.
Source of truth: `AgentConfig`, `PatchAgentRequest`, and `AgentCard` in
`litellm/types/agents.py` (plus `AgentKillSwitchConfig` on builds after
v1.103); write logic in
`litellm/proxy/agent_endpoints/agent_registry.py`.

## Contents

- Top-level fields
- agent_card_params
- litellm_params
- Completion bridge providers
- object_permission
- kill_switch (builds after v1.103)
- PATCH versus PUT
- Response fields

## Top-level fields

| Field | Type | Notes |
|---|---|---|
| `agent_name` | string | Required on create and PUT. Unique (400 on duplicate). Resolves `a2a/<agent_name>` and `/a2a/<agent_name>`. |
| `agent_card_params` | object | Required on create and PUT. See below. |
| `litellm_params` | object | Routing, backend credentials, and flags. See below. |
| `object_permission` | object | What the agent itself may use (MCP servers and tools, models, other agents). |
| `tpm_limit`, `rpm_limit` | int | Across all callers and sessions of this agent. |
| `session_tpm_limit`, `session_rpm_limit` | int | Within one session (the request's session id). |
| `static_headers` | object | Headers always sent to the backend. |
| `extra_headers` | list | Client header names forwarded to the backend. Clients can also send `x-a2a-<agent_id or name>-<header>` to forward `<header>`. |
| `access_group_ids` | list | Builds after v1.103 only; v1.103 does not store it. Unified access groups (`/v1/access_group`) this agent belongs to. |
| `kill_switch` | object | Builds after v1.103 only; v1.103 does not store it. Shutdown webhook. See below. |

## agent_card_params

An A2A AgentCard. LiteLLM stores it after a merge that fills
`version` (`1.0.0`), `skills`, `defaultInputModes`/`defaultOutputModes`
(text), and `provider` when missing; keeps only standard `capabilities`;
overwrites `securitySchemes` and `security` with LiteLLM's; and sets
`supportedInterfaces` to `<proxy>/a2a/<agent_id>`.

| Field | Notes |
|---|---|
| `url` | Backend A2A endpoint (or bridge target). Stored as given; the card served at `/a2a/<id>/.well-known/agent-card.json` shows the proxy URL instead. |
| `protocolVersion` | `"0.3"` or `"1.0"` (semver forms such as `"0.3.0"` accepted). Anything else is a 400. Unset means the card advertises `1.0`, but plain `message/send` callers without an `a2a-version` header get 0.3-shaped replies, so pin it. |
| `name`, `description` | Shown to clients. `name` defaults to `agent_name` on create. |
| `capabilities` | `{"streaming": bool, "pushNotifications": bool, "stateTransitionHistory": bool}` |
| `skills` | `[{"id", "name", "description", "tags", "examples"?}]`; used by semantic search. |
| `defaultInputModes`, `defaultOutputModes`, `iconUrl`, `documentationUrl`, `provider` | Optional card metadata. |

## litellm_params

| Key | Notes |
|---|---|
| `custom_llm_provider`, `model` | Enable the completion bridge (next section). |
| `api_key`, `aws_*`, Entra credentials, other provider secrets | Write-only: reads return `REDACTED_BY_LITELM`; echoing the marker or omitting the key keeps the stored value; an empty string clears it. |
| `require_trace_id_on_calls_to_agent` | Reject inbound calls without `x-litellm-trace-id` (400). |
| `require_trace_id_on_calls_by_agent` | Keys bound to this agent must send a trace id on their own calls. |
| `guardrails` | Guardrail names applied to calls to this agent. |
| `is_public` | Computed on reads (public AI Hub listing). Publish with `POST /v1/agents/{agent_id}/make_public`. |

## Completion bridge providers

With `custom_llm_provider` set, `message/send` and `message/stream` become a
`litellm.acompletion` call on `<custom_llm_provider>/<model>` with the card `url`
as `api_base` (`model` defaults to `agent`), so any LiteLLM provider works.
Dedicated A2A adapters exist for `pydantic_ai_agents`, Bedrock AgentCore
(`custom_llm_provider: bedrock` plus a `model` containing `agentcore`; without
that `model` the call falls through to the generic bridge), `langflow`, and
`watsonx_orchestrate`. Provider pages with full registrations:
https://docs.litellm.ai/docs/providers/langgraph,
https://docs.litellm.ai/docs/providers/bedrock_agentcore,
https://docs.litellm.ai/docs/providers/pydantic_ai_agent. Examples:

```json
{"agent_name": "langgraph-planner",
 "agent_card_params": {"name": "Planner", "url": "http://langgraph.internal:2024", "protocolVersion": "1.0"},
 "litellm_params": {"custom_llm_provider": "langgraph", "model": "agent"}}
```

```json
{"agent_name": "agentcore-research",
 "agent_card_params": {"name": "AgentCore Research", "description": "Internal research agent",
   "url": "bedrock/agentcore/arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/my-runtime"},
 "litellm_params": {"custom_llm_provider": "bedrock",
   "model": "bedrock/agentcore/arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/my-runtime",
   "aws_role_name": "arn:aws:iam::123456789012:role/LiteLLMAgentCoreInvoker", "aws_region_name": "us-east-1"}}
```

Task methods (`tasks/get`, `tasks/cancel`, push notification config) are
forwarded to the upstream URL untouched, so they fail for bridge-only agents.

## object_permission

Same shape as keys and teams; each sent field replaces that field and unsent
fields are kept.

| Field | Meaning |
|---|---|
| `mcp_servers`, `mcp_access_groups`, `mcp_toolsets` | MCP servers the agent can use. |
| `mcp_tool_permissions` | `{"<server>": ["tool", ...]}` per-server tool allowlist. |
| `models` | Models the agent may call. |
| `agents` | Other agents it may call. |

Grants that let keys and teams call the agent live on the key or team
(`object_permission.agents` with agent ids, or `agent_access_groups`), not here.

## kill_switch (builds after v1.103)

v1.103 ignores this field and `POST /v1/agents/{agent_id}/kill_switch` returns
404 there; treat the 404 as "proxy too old" and delete the agent or remove its
grants instead. On builds after v1.103:

```json
{"kill_switch": {
  "url": "https://agents.internal.example.com/agents/research/stop",
  "method": "POST",
  "headers": {"X-Source": "litellm"},
  "query_params": {"reason": "incident"},
  "body": {"graceful": true},
  "auth": {"type": "bearer", "token": "<ops-token>"}}}
```

`url` must be absolute http(s). `method`: `POST` (default), `PUT`, `PATCH`,
`DELETE`, `GET`. `auth` is one of `{"type": "bearer", "token"}`,
`{"type": "api_key", "header_name": "x-api-key", "api_key"}`, or
`{"type": "basic", "username", "password"}`; unknown keys are rejected (422).
Secrets read back as `REDACTED_BY_LITELM`, and sending the marker keeps them.
Firing returns `{agent_id, url, method, status_code, response_body, error}` and
writes a `kill_switch_fired` audit row when `store_audit_logs` is on.

## PATCH versus PUT

| Field | PATCH omitted | PATCH sent | PUT omitted |
|---|---|---|---|
| `agent_card_params` | kept | replaced whole (then merged) | required |
| `litellm_params` | kept | replaced whole, secrets restored | reset to `{}`, secrets restored |
| rate limits | kept | set; `null` clears | kept |
| `static_headers`, `extra_headers` | kept | set; `null` clears | reset to empty |
| `access_group_ids`, `kill_switch` (builds after v1.103) | kept | set; `null` clears | cleared |
| `object_permission` | kept | merged per field | kept |

## Response fields

`agent_id`, `agent_name`, `agent_card_params`, `litellm_params` (secrets
redacted), `object_permission`, `spend`, rate limits, `static_headers`,
`extra_headers`, `access_group_ids` and `kill_switch` (builds after v1.103), `keys` (keys whose
`agent_id` is this agent: `token` hash, `key_alias`, `key_name`), `created_at`,
`updated_at`, `created_by`, `updated_by`, and `search_score` on semantic search.
Non-admin readers see no `keys`, headers, or (on builds after v1.103) kill switch.
