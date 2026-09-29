---
name: litellm-connect
description: >
  Point coding agents, CLIs, SDKs, and MCP clients at a LiteLLM proxy (AI
  gateway) so their LLM calls and MCP tools go through it. Covers Claude Code,
  OpenAI Codex CLI, Gemini CLI, OpenCode, Cursor, the OpenAI and Anthropic SDKs,
  and connecting any MCP client to LiteLLM's MCP gateway. Use this whenever
  someone wants to "use LiteLLM with Claude Code", route an agent or app through
  their gateway, set ANTHROPIC_BASE_URL or OPENAI_BASE_URL to LiteLLM, add
  LiteLLM MCP tools to Claude Code or Cursor, or asks which models their key
  can call, even if they only say "connect", "hook up", or "use my proxy".
license: MIT
compatibility: Requires curl. Written against LiteLLM v1.103 (September 2026).
metadata:
  author: BerriAI
  version: "2.0"
allowed-tools: Bash(curl:*) Bash(python3:*)
---

# Connect clients to LiteLLM

The gateway speaks the OpenAI API (`/v1/chat/completions`, `/v1/responses`),
the Anthropic API (`/v1/messages`), the Gemini API, and MCP. So most clients
connect by swapping their base URL and using a LiteLLM virtual key as the API
key.

## What you need

1. **Gateway URL**, e.g. `http://localhost:4000` or `https://llm.example.com`.
   Use `LITELLM_BASE_URL` if it is set.
2. **A virtual key for the client.** Don't wire the master key into a tool.
   If the user doesn't have one, create a scoped key with **litellm-keys**
   (`key_type: "llm_api"`, a budget, the models this client needs).
3. **Model names that exist on the gateway.** Clients must send a LiteLLM
   `model_name`, not the provider's id, unless the gateway defines that exact
   name. Check what the key can call:

```bash
curl -sS "$LITELLM_BASE_URL/v1/models" -H "Authorization: Bearer <client key>" \
  | python3 -c "import sys,json; print('\n'.join(m['id'] for m in json.load(sys.stdin)['data']))"
```

`/v1/models` only lists models this key can reach (on builds after v1.103,
models marked `discoverable: false` are also hidden but still callable). Pick the client below and
use one of these names.

## Claude Code

```bash
export ANTHROPIC_BASE_URL="$LITELLM_BASE_URL"     # no /v1 suffix
export ANTHROPIC_AUTH_TOKEN="<client key>"
export ANTHROPIC_MODEL="<model_name from /v1/models>"
unset ANTHROPIC_API_KEY                           # otherwise Claude Code sends it instead
claude
```

To make it permanent, put the same values in the `env` block of
`~/.claude/settings.json`. Useful extras:

- `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`,
  `ANTHROPIC_DEFAULT_HAIKU_MODEL` map Claude Code's tiers to gateway names, so
  `/model` choices resolve (any provider works, not only Anthropic).
- `CLAUDE_CODE_SUBAGENT_MODEL` sets the model subagents use; point it at a
  gateway name too if the tier variables don't cover it.
- `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` fills the `/model` picker from
  the gateway's `/v1/models` (Claude Code 2.1.129+).
- Using a Claude subscription and only want LiteLLM for tracking? Send the
  LiteLLM key as a header instead:
  `ANTHROPIC_CUSTOM_HEADERS="x-litellm-api-key: Bearer <client key>"`.

If the gateway URL is plain `http://` on anything other than localhost or a
private network (VPN, tailnet), say so: the key travels in cleartext. Inside
Claude Code, `/status` shows the base URL and model it is actually using.

`Invalid model name passed in` means Claude Code sent a model id the gateway
doesn't define; set the tier variables or add that name with **litellm-models**.

## OpenAI Codex CLI

`~/.codex/config.toml`:

```toml
model = "<model_name>"
model_provider = "litellm"

[model_providers.litellm]
name = "LiteLLM"
base_url = "http://localhost:4000/v1"
env_key = "LITELLM_API_KEY"
wire_api = "responses"
```

Then `export LITELLM_API_KEY=<client key>` and run `codex`.

## Gemini CLI

```bash
export GOOGLE_GEMINI_BASE_URL="$LITELLM_BASE_URL"
export GEMINI_API_KEY="<client key>"
gemini -m <model_name>
```

## OpenCode

In `~/.config/opencode/opencode.json`, add an OpenAI-compatible provider whose
model keys equal gateway `model_name`s, then add the key with `/connect`:

```json
{
  "provider": {
    "litellm": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "LiteLLM",
      "options": { "baseURL": "http://localhost:4000/v1" },
      "models": { "gpt-5.5": {}, "claude-sonnet-5-5": {} }
    }
  }
}
```

## Cursor

Settings, Models: enable "Override OpenAI Base URL", set it to
`<gateway URL>/cursor` (LiteLLM v1.97+), and paste the client key as the OpenAI
API key. Cursor calls from its own servers, so the gateway must be reachable
from the internet; `localhost` will not work.

## SDKs

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:4000/v1", api_key="<client key>")
client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "hi"}])

import anthropic
claude = anthropic.Anthropic(base_url="http://localhost:4000", api_key="<client key>")
claude.messages.create(model="claude-sonnet-5-5", max_tokens=100,
                       messages=[{"role": "user", "content": "hi"}])
```

Any OpenAI-compatible framework (LangChain, LlamaIndex, Vercel AI SDK, Pydantic
AI, the OpenAI Agents SDK) connects the same way: base URL plus client key.

## MCP gateway

LiteLLM exposes the MCP servers registered on it (see **litellm-mcp**) over
streamable HTTP.

| URL | Gives the client |
|---|---|
| `<gateway>/mcp` | Every server the key may use; narrow with header `x-mcp-servers: github,jira` |
| `<gateway>/<server_name>/mcp` | One server (`/github,jira/mcp` for several) |
| `<gateway>/toolset/<toolset_name>/mcp` | One curated toolset |

Authenticate with `x-litellm-api-key: Bearer <client key>`. Prefer it over
`Authorization`, which stays free for servers that do their own OAuth.

```bash
# Claude Code
claude mcp add --transport http litellm_github \
  "$LITELLM_BASE_URL/github/mcp" \
  --header "x-litellm-api-key: Bearer <client key>"
```

Cursor, in `~/.cursor/mcp.json`:

```json
{ "mcpServers": { "litellm": {
    "url": "http://localhost:4000/mcp",
    "headers": { "x-litellm-api-key": "Bearer <client key>" } } } }
```

For Codex, add `[mcp_servers.litellm]` with `url = "<gateway>/<server>/mcp"`
and `bearer_token_env_var = "LITELLM_API_KEY"` (a literal `bearer_token` is not
supported).

"The key is not allowed to access the requested MCP servers" means the key
has no grant: add the server to the key's or team's
`object_permission.mcp_servers` (**litellm-mcp** covers this), or register the
server with `allow_all_keys: true`.

## Verify end to end

```bash
curl -sS "$LITELLM_BASE_URL/v1/chat/completions" \
  -H "Authorization: Bearer <client key>" -H "Content-Type: application/json" \
  -d '{"model":"<model_name>","messages":[{"role":"user","content":"say ok"}],"max_tokens":5}'
```

Then run one prompt in the client and confirm the request shows up in spend
(**litellm-usage**) under that key.

## Errors

| Symptom | Likely cause |
|---|---|
| 401 | Wrong key, or the tool is sending a different variable (e.g. `ANTHROPIC_API_KEY` still set). |
| 400 `Invalid model name passed in` | Model name not defined on the gateway. |
| 403 `key_model_access_denied` | The model exists but is not in the key's (or its team's) `models`. |
| 429 or 422 with `"type": "budget_exceeded"` | Budget exceeded (v1.103 returns 429, builds after v1.103 return 422). Check with **litellm-keys**, **litellm-budgets**, or **litellm-doctor**. |
| 429 without that type | Key, user, or team rate limit (rpm/tpm) hit. |
| Client can't reach gateway | Base URL has or lacks `/v1` for that client (Claude Code: none; Codex/OpenCode/OpenAI SDK: `/v1`). |
