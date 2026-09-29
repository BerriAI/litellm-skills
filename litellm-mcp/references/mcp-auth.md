# MCP server auth payloads

How LiteLLM authenticates to the upstream MCP server, per `auth_type`, as REST
bodies for `POST /v1/mcp/server` (LiteLLM v1.103). The LiteLLM key a client
uses to reach the gateway is never forwarded upstream; only the credential
below is. Source: `MCPAuth` and `MCPCredentials` in `litellm/types/mcp.py`.

## Contents

- Static credentials
- AWS SigV4
- OAuth2 machine-to-machine (client_credentials)
- OAuth2 interactive (authorization_code)
- Token exchange / On-Behalf-Of
- ID-JAG
- Client-forwarded tokens (true_passthrough, oauth_delegate)
- Extra credential keys

## Static credentials

All take `credentials: {"auth_value": "<secret>"}`.

| `auth_type` | Sent upstream |
|---|---|
| `none` (or omit) | Nothing. |
| `bearer_token` | `Authorization: Bearer <auth_value>` |
| `api_key` | `X-API-Key: <auth_value>` |
| `basic` | `Authorization: Basic base64(<auth_value>)`; `auth_value` is raw `username:password` |
| `token` | `Authorization: token <auth_value>` (GitHub-style scheme) |
| `authorization` | `Authorization: <auth_value>` verbatim, scheme included |

```json
{"server_name": "inventory", "transport": "http", "url": "https://mcp.internal.example.com/mcp",
 "auth_type": "api_key", "credentials": {"auth_value": "<inventory-api-key>"}}
```

For a different header name or several fixed headers, use `static_headers`
(optionally with `${ENV_VAR}` placeholders from `env_vars`) with
`auth_type: none`. To let each user or key bring their own upstream token for a
shared server, use `is_byok` or per-user env vars (see `fields.md`).

## AWS SigV4

`auth_type: aws_sigv4` signs every request (for example Bedrock AgentCore MCP
endpoints). Region and service are required; keys are optional and fall back to
the proxy's boto3 credential chain.

```json
{"server_name": "agentcore_tools", "transport": "http",
 "url": "https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/<arn>/invocations",
 "auth_type": "aws_sigv4",
 "credentials": {"aws_region_name": "us-east-1", "aws_service_name": "bedrock-agentcore",
                 "aws_role_name": "arn:aws:iam::123456789012:role/McpInvoker",
                 "aws_session_name": "litellm-mcp"}}
```

Also accepted: `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`.
STS AssumeRole (`aws_role_name`) needs v1.83.3+.

## OAuth2 machine-to-machine (client_credentials)

LiteLLM fetches, caches, and refreshes one token for the server.

```json
{"server_name": "billing_api", "transport": "http", "url": "https://mcp.billing.example.com/mcp",
 "auth_type": "oauth2", "oauth2_flow": "client_credentials",
 "token_url": "https://auth.example.com/oauth/token",
 "credentials": {"client_id": "<client-id>", "client_secret": "<client-secret>", "scopes": ["mcp.read"]}}
```

If `oauth2_flow` is omitted on an `oauth2` create, LiteLLM stores
`client_credentials` when `token_url`, `client_id`, and `client_secret` are
present and `authorization_url` is not; otherwise `authorization_code`. Send it
explicitly. `credentials.token_endpoint_auth_method` may be
`client_secret_basic` (default is `client_secret_post`).

## OAuth2 interactive (authorization_code)

Each end user signs in to the upstream (GitHub, Linear, Atlassian, Slack) and
LiteLLM stores a per-user token. The admin only registers the server; the skill
cannot complete a user's browser sign-in.

```json
{"server_name": "linear", "transport": "http", "url": "https://mcp.linear.app/mcp",
 "auth_type": "oauth2", "oauth2_flow": "authorization_code"}
```

With no endpoints set, LiteLLM discovers them (RFC 9728 then RFC 8414) and uses
dynamic client registration. Set `authorization_url`, `token_url`,
`registration_url`, `issuer`, and `credentials.client_id` / `client_secret`
when the upstream needs a pre-registered app. Related flags:

| Field | Meaning |
|---|---|
| `delegate_auth_to_upstream` | The MCP client runs the PKCE flow against the upstream itself (v1.85+). Honored only for `oauth2`. |
| `per_server_oauth_discovery` | Serve OAuth discovery per server. Only valid with `oauth2` + `authorization_code` and without `delegate_auth_to_upstream`; otherwise 422 on create, 400 on update. |

`oauth_passthrough: true` (v1.89+) is the non-oauth2 counterpart: with
`auth_type` `none` and `"Authorization"` in `extra_headers`, LiteLLM proxies the
upstream's protected-resource metadata, emits 401 challenges when no bearer is
sent, and relays upstream 401/403 instead of swallowing them.

Users see their connection status with
`GET /v1/mcp/server/{id}/oauth-user-credential/status`. Changing `url`,
`issuer`, or the auth family later deletes every stored user token.

## Token exchange / On-Behalf-Of

`auth_type: oauth2_token_exchange` exchanges the caller's IdP token (RFC 8693)
for one scoped to the MCP server. Config-file support arrived in v1.85; REST
and dashboard support in v1.93.

```json
{"server_name": "internal_tools", "transport": "http", "url": "https://mcp.internal.example.com/mcp",
 "auth_type": "oauth2_token_exchange",
 "token_exchange_endpoint": "https://idp.example.com/oauth2/token",
 "audience": "api://internal-tools-mcp",
 "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
 "token_exchange_profile": "rfc8693",
 "credentials": {"client_id": "<idp-client-id>", "client_secret": "<idp-client-secret>", "scopes": ["tools.read"]}}
```

`token_exchange_profile: entra_obo` switches to Microsoft Entra's On-Behalf-Of
grant; there `audience` and `subject_token_type` are unused and the target
resource goes in `scopes`. Send these four settings top level; the same keys
inside `credentials` are a legacy shape that is migrated on write.

## ID-JAG

`auth_type: oauth2_id_jag` (v1.94+) turns the user's SSO `id_token` into an
Identity Assertion JWT (leg 1) and then an access token at the resource
authorization server (leg 2), e.g. Okta cross-app access. Over REST, the leg-2
and signing settings go inside `credentials`:

```json
{"server_name": "okta_tools", "transport": "http", "url": "https://mcp.example.com/mcp",
 "auth_type": "oauth2_id_jag",
 "token_exchange_endpoint": "https://your-org.okta.com/oauth2/v1/token",
 "audience": "https://your-org.okta.com/oauth2/<custom-as-id>",
 "credentials": {"client_id": "<okta-client-id>",
   "id_jag_resource_token_endpoint": "https://your-org.okta.com/oauth2/<custom-as-id>/v1/token",
   "client_private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----",
   "client_private_key_id": "<jwks-kid>", "scopes": ["mcp.tools.read"]}}
```

Optional: `id_jag_resource`, `client_assertion_signing_alg` (default `RS256`),
`client_secret` (fallback when no private key). It only works for users who
signed in through SSO, since leg 1 needs their `id_token`.

## Client-forwarded tokens (true_passthrough, oauth_delegate)

Both (v1.93+) forward the caller's upstream token verbatim and store none.

| `auth_type` | LiteLLM admission | Caller sends |
|---|---|---|
| `true_passthrough` | None; the upstream is the only gate | Upstream token in `Authorization` |
| `oauth_delegate` | Required (LiteLLM key, SSO, or JWT) | LiteLLM credential plus a separate upstream bearer |

`dcr_bridge: true` (only valid with these two types) makes LiteLLM host OAuth
discovery and registration for clients such as Claude Code, Cursor, and
OpenCode that cannot register with the upstream IdP themselves. Since these
servers hold no token, `test/tools/list` and pinning (builds after v1.103) need a token supplied at
test time; tell the user to use the dashboard's "Authorize & Fetch Tools"
button if the API test cannot list tools. From v1.103, legacy delegated
integrations that were not admitted receive 401 until migrated to
`oauth_delegate`.

## Extra credential keys

| Key | Use |
|---|---|
| `upstream_token_header` | Send the resolved credential in a header other than `Authorization`. |
| `upstream_resource` | RFC 8707 resource indicator on OAuth legs; `"auto"` derives it from `url`. |
| `token_endpoint_auth_method` | `client_secret_basic` or `client_secret_post`. |

Credentials are encrypted at rest and every read returns them redacted, so a
lost secret cannot be recovered through the API; set a new one with `PUT`.
