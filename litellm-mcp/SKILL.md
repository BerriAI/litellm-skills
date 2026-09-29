---
name: litellm-mcp
description: >
  Register, test, update, and remove MCP servers on a live LiteLLM proxy (AI
  gateway) with curl, and control who can use their tools. Use this whenever
  someone wants to add an MCP server (GitHub, Linear, Slack, Jira, an internal
  tool server, an OpenAPI spec, or a stdio npx/uvx server) to LiteLLM; rotate an
  MCP server's token or change its URL or auth; check whether an MCP server is
  healthy or list and call its tools; import a Claude Desktop or Claude Code
  mcpServers JSON; restrict which tools are exposed; build a toolset; grant a
  key or team access to MCP servers or specific tools; see or kill live MCP
  sessions; or delete a server. Also use it when a user says "MCP gateway",
  "tools aren't showing up", or asks why a key cannot call a tool.
license: MIT
compatibility: Requires curl and python3. Written against LiteLLM v1.103 (September 2026).
metadata:
  author: BerriAI
  version: "2.0"
allowed-tools: Bash(curl:*) Bash(python3:*)
---

# LiteLLM MCP servers

LiteLLM fronts upstream MCP servers: it holds their credentials, prefixes their
tools with the server name, and decides per key and team which tools each
caller sees. Clients connect to one gateway URL instead of every server.

## Connect

Read `LITELLM_BASE_URL` and `LITELLM_API_KEY` from the environment. If either is
missing, ask for it once and export it for the rest of the session. Registering,
testing, editing, pinning, and deleting servers and toolsets needs a proxy admin
key; granting access on keys and teams also works with a team admin key for that
team. Never echo the admin key or an upstream token back into logs you don't
need to.

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
| Try a server before saving it | `POST /mcp-rest/test/connection`, `POST /mcp-rest/test/tools/list` |
| Register a server | `POST /v1/mcp/server` |
| Import a Claude `mcpServers` JSON | `POST /v1/mcp/server/import` (v1.100+) |
| List or inspect servers | `GET /v1/mcp/server`, `GET /v1/mcp/server/{server_id}` |
| Check health, list or call tools | `GET /v1/mcp/server/health`, `GET /mcp-rest/tools/list`, `POST /mcp-rest/tools/call` |
| Change URL, auth, allowed tools | `PUT /v1/mcp/server` |
| Freeze the tool catalog (builds after v1.103) | `POST` / `DELETE /v1/mcp/server/{server_id}/pin` |
| Curate tools across servers | `/v1/mcp/toolset` (v1.83.3+) |
| Give a key or team access | `POST /key/update`, `POST /team/update` with `object_permission` |
| See or force-close live sessions | `GET` / `DELETE /v1/mcp/sessions` (v1.103+) |
| Remove a server | `DELETE /v1/mcp/server/{server_id}` |

## Register a server

Ask for what the request needs:

1. `server_name`: letters, digits, underscores (`github_mcp`). A `-` is rejected
   with 400 because LiteLLM uses it to join server and tool names
   (`github_mcp-create_issue`). `alias` defaults to the name; spaces become `_`.
2. `transport`: `http` (streamable HTTP, what most current servers speak), `sse`,
   or `stdio`. It defaults to `sse` when omitted, so send `http` explicitly for
   streamable HTTP servers.
3. `url` for `http`/`sse`, or `spec_path` (URL or path to an OpenAPI spec, with
   `url` as the API base) to turn a REST API into MCP tools.
4. Auth: `auth_type` plus a `credentials` object. For a static token it is
   `{"auth_value": "..."}`; OAuth2, token exchange, SigV4, and passthrough modes
   take other fields. Read `references/mcp-auth.md` before any auth type other
   than `none`, `bearer_token`, or `api_key`.
5. Optional: `description`, `allowed_tools` (expose only these), `mcp_access_groups`,
   `allow_all_keys` (every key may use it without a grant).

Test with the exact body first. Both test routes return HTTP 200 even when the
upstream fails, so read the body: `"status": "ok"` on success, or
`"status": "error"` with a `message`.

```bash
BODY='{
  "server_name": "github_mcp",
  "description": "GitHub issues and pull requests",
  "transport": "http",
  "url": "https://api.githubcopilot.com/mcp/",
  "auth_type": "bearer_token",
  "credentials": {"auth_value": "<github-pat>"},
  "mcp_access_groups": ["dev_tools"]
}'

curl -sS -X POST "$LITELLM_BASE_URL/mcp-rest/test/tools/list" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" -d "$BODY"

curl -sS -X POST "$LITELLM_BASE_URL/v1/mcp/server" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' -d "$BODY"
```

Create returns 201 with the record (credentials redacted). Show `server_id`,
`server_name`, `transport`, and `url`; grants and tool calls use the id or name.

**stdio servers** take `command`, a non-empty `args` list, optional `env`, and no
`url`, e.g. `"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"]`.
`command` must be `npx`, `uvx`, `python`, `python3`, `node`, `docker`, or `deno`
(extendable with `LITELLM_MCP_STDIO_EXTRA_COMMANDS`), and it runs on the proxy
host, so the binary has to exist inside the proxy container.

Timeouts, concurrency caps, env vars, tool renames, and every other field are
in `references/fields.md`.

## Import from Claude JSON (v1.100+)

`POST /v1/mcp/server/import` takes `{"mcpServers": {...}}` (Claude Desktop and
Claude Code config) or `{"mcp_servers": [...]}` (Anthropic Messages API). Names
are sanitized to `[A-Za-z0-9_]`; `authorization_token` becomes a bearer token.
The response lists `imported` (with `server_id`), `skipped` (name already exists),
and `errors` per entry, so report all three.

## Inspect, health, and tools

```bash
curl -sS "$LITELLM_BASE_URL/v1/mcp/server" -H "Authorization: Bearer $LITELLM_API_KEY"
# one server: /v1/mcp/server/<server_id>
# status: healthy | unhealthy | unknown (builds after v1.103 also accept
# include_reachability=true, which adds "reachable")
curl -sS "$LITELLM_BASE_URL/v1/mcp/server/health?server_ids=<server_id>" \
  -H "Authorization: Bearer $LITELLM_API_KEY"

curl -sS "$LITELLM_BASE_URL/mcp-rest/tools/list?server_id=<server_id>" \
  -H "Authorization: Bearer $LITELLM_API_KEY"

curl -sS -X POST "$LITELLM_BASE_URL/mcp-rest/tools/call" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"server_id": "<server_id>", "name": "list_issues", "arguments": {"owner": "BerriAI", "repo": "litellm"}}'
```

When a server is unhealthy, quote `health_check_error` from
`GET /v1/mcp/server/<server_id>` verbatim (for example `[Errno -2] Name or
service not known` is DNS, `Connection refused` is the port); it is more useful
than "unreachable".

To answer "why can't this key see the tool", run the same `tools/list` with the
user's key instead of the admin key: it returns only what that key may call.
MCP clients connect at `$LITELLM_BASE_URL/mcp` (all permitted servers),
`/<server_name>/mcp` (one server), or `/toolset/<toolset_name>/mcp`, sending the
LiteLLM key as `x-litellm-api-key: Bearer sk-...`; the `litellm-connect` skill
covers client setup.

## Update a server

`PUT /v1/mcp/server` with `server_id` plus only the fields that change. On
v1.88+ it is a partial update: omitted fields keep their stored value and an
explicit `null` clears one. Before v1.88 every omitted field reset to its
default (`transport` back to `sse`, `allow_all_keys` to false, access groups
emptied), so on an older proxy GET the record and resend all of it, including
credentials, which GET returns redacted.

```bash
curl -sS -X PUT "$LITELLM_BASE_URL/v1/mcp/server" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"server_id": "<server_id>", "credentials": {"auth_value": "<new-token>"}}'
```

Returns 202 with the updated record. Things that surprise people:

- Sending `transport` of `http` or `sse` requires `url` or `spec_path` in the
  same body, so leave `transport` out unless it is changing.
- `credentials` merges key by key into the stored object while the auth type
  stays in the same family. Changing `auth_type` without new `credentials`
  wipes the stored ones.
- Changing `url`, `auth_type`, or the OAuth issuer clears discovered OAuth
  endpoints and deletes every user's stored OAuth token for the server, so
  users must authorize again. Warn before doing it.
- `allowed_tools` replaces the list. `config.yaml` servers (`is_config: true`)
  are read-only here.

**Pin tools** (admin, builds after v1.103): `POST /v1/mcp/server/{server_id}/pin`
freezes the current tool names, descriptions, and schemas, so an upstream
change raises an `mcp_pinned_tools_changed` alert instead of reaching clients;
`DELETE` unpins. v1.103 has no pinning and returns 404 on this route; treat
that as "proxy too old" and use `allowed_tools` to limit what clients see.

## Toolsets and access

A toolset is a named list of `{server_id, tool_name}` pairs that is granted as a
unit and served at `/toolset/<name>/mcp`; its CRUD calls are in
`references/fields.md`.

Access lives in `object_permission` on keys and teams:

```bash
curl -sS -X POST "$LITELLM_BASE_URL/key/update" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"key_alias": "support-bot-prod", "object_permission": {
        "mcp_servers": ["github_mcp"],
        "mcp_tool_permissions": {"github_mcp": ["list_issues", "get_issue"]}}}'
```

Each field you send replaces that field's stored list and other fields are
kept, so to add a server, read the current list first (`GET /key/info`, under
`info.object_permission`; `GET /team/info` for teams) and send the union. Fields,
the `no-mcp-servers` sentinel, and how key and team grants intersect are in
`references/fields.md`. A key inside a team can only be granted servers the team
allows or `allow_all_keys` servers; anything else is a 403.

## Sessions (v1.103+)

`GET /v1/mcp/sessions` lists live gateway sessions; `DELETE /v1/mcp/sessions?user_id=<id>`
(or `?session_id_prefix=`) force-closes them. Both act on the one worker that
answers, so with several replicas say so. Details in `references/fields.md`.

## Delete a server

GET `/v1/mcp/server/{server_id}` first and show `server_name`, `url`, and
`transport`, then get an explicit yes. Deletion removes the server and its tools
for every client at once. Key, team, and agent grants that name it
(`object_permission.mcp_servers`, `mcp_tool_permissions`) and toolset entries
that point at it are not cleaned up, and clients configured with
`/<server_name>/mcp` start failing.

```bash
curl -sS -X DELETE "$LITELLM_BASE_URL/v1/mcp/server/<server_id>" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -w '\nHTTP %{http_code}\n'
```

Success is 202 with an empty body; 404 means the id does not exist or the
server comes from `config.yaml`.

## Errors

- **400 "Server name cannot contain '-'"**: use underscores in `server_name`/`alias`.
- **400 "already exists"**: names and aliases are unique case-insensitively.
- **422 "url or spec_path is required for HTTP/SSE transport"**, **"command is
  required for stdio transport"**, **"args is required"**, or **"not in the
  allowed commands list"**: fix the transport fields.
- **422 or 400 mentioning `dcr_bridge` or `per_server_oauth_discovery`**: those
  flags only work with specific auth types; see `references/mcp-auth.md`.
- **403 "only ... PROXY_ADMIN"**: server writes, tests, pins (builds after
  v1.103), and toolset writes need a proxy admin key.
- **Test route returns `"status": "error"`**: the upstream is unreachable, the
  transport is wrong (try `http` versus `sse`), or the credential is rejected.
- **500 "Database not connected"**: MCP management needs the proxy database.
- Anything else: show `detail` / `error` verbatim and the likely fix. Docs:
  https://docs.litellm.ai/docs/mcp and https://docs.litellm.ai/docs/mcp_grant_access
