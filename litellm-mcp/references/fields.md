# MCP server fields

Fields accepted by `POST /v1/mcp/server`, `PUT /v1/mcp/server`, and the two
`/mcp-rest/test/*` routes (LiteLLM v1.103). Send only what the user asked for.
Source of truth: `NewMCPServerRequest` / `UpdateMCPServerRequest` in
`litellm/proxy/_types.py` and `MCPCredentials` in `litellm/types/mcp.py`.
Auth-specific fields are in `mcp-auth.md`.

## Contents

- Identity and transport
- Tools
- Headers, env vars, and limits
- Visibility
- Update semantics
- Toolsets
- Granting access (object_permission)
- Per-user env vars
- Sessions
- Other admin routes

## Identity and transport

| Field | Type | Notes |
|---|---|---|
| `server_id` | string | Optional on create (a UUID is generated). The reserved ids `all-team-mcpservers` and `all-proxy-mcpservers` are rejected. Required on `PUT`. |
| `server_name` | string | No `-` (it is `MCP_TOOL_PREFIX_SEPARATOR`). Unique, case-insensitive. |
| `alias` | string | Tool prefix and path segment (`/<alias>/mcp`). Defaults to `server_name`; spaces become `_`; no `-`. |
| `description` | string | Shown in the UI and to clients. |
| `transport` | `sse` \| `http` \| `stdio` | Defaults to `sse`. `http` is streamable HTTP. |
| `url` | string | Required for `http`/`sse` unless `spec_path` is set. URL userinfo (`user:pass@`) is rejected with `auth_type: none`; use `basic`. |
| `spec_path` | string | OpenAPI spec path or URL; each `operationId` becomes a tool. Remote specs pass SSRF checks (private IPs rejected unless allowlisted). |
| `command`, `args`, `env` | string, list, object | stdio only. `args` must be non-empty; `command` basename must be in the stdio allowlist. |
| `mcp_info` | object | Free-form metadata (e.g. `logo_url`). On builds after v1.103, `mcp_info.protocol_version` may pin `2024-11-05`, `2025-03-26`, `2025-06-18`, `2025-11-25`, or `auto`; v1.103 ignores it and only honors the client's protocol version header. |
| `instructions` | string | Server instructions surfaced to clients from `InitializeResult` (v1.83.10+). |
| `source_url` | string | Where the server came from (docs or repo link). |

## Tools

| Field | Type | Notes |
|---|---|---|
| `allowed_tools` | list | Expose only these upstream tool names. Replaced wholesale on update. |
| `tool_name_to_display_name` | object | Rename tools for clients. Values must match Bedrock's tool-name pattern (letters, digits, `_`, `-`). |
| `tool_name_to_description` | object | Override tool descriptions. |

Tool pinning (builds after v1.103) is a separate route
(`POST`/`DELETE /v1/mcp/server/{id}/pin`), not a field. On those builds the
response's `pinned_tools` shows the frozen catalog; v1.103 has neither.

## Headers, env vars, and limits

| Field | Type | Notes |
|---|---|---|
| `static_headers` | object | Headers sent on every upstream request. May reference env vars as `${NAME}`. |
| `extra_headers` | list | Header names forwarded from the client request to the upstream. |
| `env_vars` | list | `[{"name": "JIRA_TOKEN", "value": "...", "scope": "global" \| "user", "description": "..."}]` (v1.89+). `scope: user` means each user supplies their own value (see Per-user env vars). |
| `timeout` | float (seconds) | Per-server upstream timeout. |
| `max_concurrent_requests` | int | Cap on in-flight upstream calls for this server (v1.93+). |

## Visibility

| Field | Type | Notes |
|---|---|---|
| `mcp_access_groups` | list | Group names; granting a group grants every server in it. Clients can target a group with `/mcp/<group>` or `x-mcp-servers: <group>`. |
| `allow_all_keys` | bool | Default false. True makes the server usable by every key without a grant. |
| `available_on_public_internet` | bool | Default true. False restricts the server to callers from internal IP ranges. |
| `is_byok`, `byok_description`, `byok_api_key_help_url` | bool, list, string | Bring-your-own-key: each user stores their own upstream key via `POST /v1/mcp/server/{id}/user-credential`. |

## Update semantics

`PUT /v1/mcp/server` returns 202 and the updated record.

- v1.88+ (PR #29253): partial. Omitted fields keep their stored value; explicit
  `null` clears. Before v1.88 omitted fields reset to defaults: `transport` to
  `sse`, `allow_all_keys` false, `available_on_public_internet` true,
  `mcp_access_groups` and `args` empty.
- The transport validator runs on the raw body: sending `transport: http|sse`
  without `url`/`spec_path`, or `transport: stdio` without `command` and `args`,
  is a 422 even if the stored row has them.
- `credentials` is merged into the stored object when the auth family is
  unchanged (e.g. rotating only `auth_value` or only `aws_region_name`). A switch
  between families (say `oauth2` to `bearer_token`) replaces it, and changing
  `auth_type` without sending `credentials` clears it.
- A change to `url`, `auth_type` family, or `issuer` resets discovered OAuth
  endpoints, and any change to what an OAuth token is minted for purges every
  user's stored OAuth token for the server.
- `dcr_bridge: true` on update is checked against the stored `auth_type` when
  the body omits it (400 if the stored type is not `true_passthrough` or
  `oauth_delegate`).

## Toolsets

A toolset is `{toolset_name, description, tools: [{server_id, tool_name}]}` with
unprefixed tool names. Admin-only writes; `GET` returns what the calling key is
granted (admins see all).

```bash
curl -sS -X POST "$LITELLM_BASE_URL/v1/mcp/toolset" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"toolset_name": "support_readonly", "description": "Read-only GitHub and Linear tools",
       "tools": [{"server_id": "<github-server-id>", "tool_name": "get_issue"},
                 {"server_id": "<linear-server-id>", "tool_name": "list_issues"}]}'
```

| Call | Result |
|---|---|
| `POST /v1/mcp/toolset` | 201 with `toolset_id`; 409 if the name exists |
| `GET /v1/mcp/toolset`, `GET /v1/mcp/toolset/{id}` | list / one (403 for a non-admin key without the grant) |
| `PUT /v1/mcp/toolset` | body `{toolset_id, ...}`; partial, but `tools` is replaced when sent (send `[]` to empty it) |
| `DELETE /v1/mcp/toolset/{id}` | 202; grants listing the id are not cleaned up |

Clients reach a toolset at `/toolset/<toolset_name>/mcp`. Since v1.100 a toolset
attached to a team, organization, or internal user is enforced (before that it
was ignored at those levels).

## Granting access (object_permission)

Same block on `/key/generate`, `/key/update`, `/team/new`, `/team/update`,
`/organization/*`, `/user/*`, and agents.

| Field | Type | Meaning |
|---|---|---|
| `mcp_servers` | list | Server ids or names. `["no-mcp-servers"]` blocks all MCP access. |
| `mcp_access_groups` | list | Every server in these groups. |
| `mcp_toolsets` | list | Toolset ids. |
| `mcp_tool_permissions` | object | `{"<server id or name>": ["tool", ...]}`; a server listed here counts as granted. |
| `blocked_tools` | list | Tool names never callable by this entity. |
| `mcp_tool_search_enabled` | bool | Expose the `mcp_tool_search` virtual tool for large catalogs (v1.92+). |

Updates merge per field: a sent field replaces that field, unsent fields stay.
How it resolves: a key with no MCP grant inherits its team's; when both set
servers, the key gets the intersection, and tool lists intersect per server.
Within one level, toolsets and `mcp_tool_permissions` are unioned first. A key
in a team can only be granted servers the team allows or `allow_all_keys`
servers (403 otherwise); a proxy admin can grant anything to a key with no
team. Per-key rate limits per server use `mcp_rpm_limit` on the key
(`{"github_mcp": 20}`, v1.89+).

## Per-user env vars

For `env_vars` entries with `scope: user`, each user stores values with their
own key (not the admin's): `POST /v1/mcp/server/{id}/user-env-vars` with
`{"values": {"JIRA_TOKEN": "..."}}` (merged over stored values; unknown names
ignored), `GET` for status (`missing_count`), `DELETE` to clear.
`GET /v1/mcp/user-env-vars/status` shows every server with missing values.

## Sessions

`GET /v1/mcp/sessions` needs a proxy admin or view-only admin and reports live
stateful sessions on the answering worker, grouped by AI client and by user.
`DELETE /v1/mcp/sessions` needs a full proxy admin and at least one of
`session_id_prefix` (minimum length enforced) or `user_id` as query parameters;
omitting both is a 400.

## Other admin routes

| Route | Purpose |
|---|---|
| `GET /v1/mcp/access_groups` | List MCP access group names. |
| `GET /v1/mcp/discover` | Curated catalog of well-known MCP servers. |
| `POST /v1/mcp/server/register`, `GET /v1/mcp/server/submissions`, `PUT /v1/mcp/server/{id}/approve` or `/reject` | Non-admin submissions and the admin review queue (stdio cannot be submitted). |
| `POST /v1/mcp/make_public` | `{"mcp_server_ids": [...]}` to list servers on the public AI Hub. |
| `GET /v1/mcp/server/{id}/user-credentials` | Which users hold a stored BYOK or OAuth credential (no secrets). |
| `DELETE /v1/mcp/server/{id}/oauth-user-credential?user_id=` | Admin revokes one user's stored OAuth token. |
