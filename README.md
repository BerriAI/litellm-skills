# litellm skills

[Agent Skills](https://agentskills.io) that let coding agents (Claude Code, Codex, OpenCode, Cursor, and anything else that reads `SKILL.md`) run, connect to, and administer a [LiteLLM](https://github.com/BerriAI/litellm) proxy. Every skill works over plain HTTP with `curl`, so there is nothing to install on the proxy side.

## Install

Claude Code plugin:

```
/plugin marketplace add BerriAI/litellm-skills
/plugin install litellm@litellm
```

Any agent, via the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add BerriAI/litellm-skills
```

Or clone and symlink into `~/.claude/skills` (set `SKILLS_DIR` to target another agent's skills directory). Re-running it updates the skills and removes links left by older versions.

```bash
curl -fsSL https://raw.githubusercontent.com/BerriAI/litellm-skills/main/install.sh | sh
```

Then tell the agent where your proxy is:

```bash
export LITELLM_BASE_URL=https://litellm.example.com
export LITELLM_API_KEY=sk-...   # proxy admin key for admin tasks, any virtual key for litellm-connect
```

## Skills

| Skill | Use it to |
|---|---|
| [`litellm-setup`](litellm-setup/) | Run a proxy with Docker Compose, `docker run`, or uv, with Postgres and safe master and salt keys. |
| [`litellm-connect`](litellm-connect/) | Point Claude Code, Codex, Gemini CLI, OpenCode, Cursor, the OpenAI and Anthropic SDKs, and MCP clients at the gateway. |
| [`litellm-doctor`](litellm-doctor/) | Check health and version, and explain 401/403/404/429/500s and why a key can't call a model. |
| [`litellm-keys`](litellm-keys/) | Create, update, rotate, block, and delete virtual keys with budgets, rate limits, and model access. |
| [`litellm-users`](litellm-users/) | Create, update, invite, and delete users, including bulk onboarding. |
| [`litellm-teams`](litellm-teams/) | Manage teams, members, per-member budgets, and team model access. |
| [`litellm-orgs`](litellm-orgs/) | Manage organizations and org admins (Enterprise). |
| [`litellm-models`](litellm-models/) | Add, test, update, pause, and delete models; reusable credentials, access groups, fallbacks. |
| [`litellm-mcp`](litellm-mcp/) | Register, test, and update MCP servers (HTTP, SSE, stdio, OAuth), toolsets, and MCP access grants. |
| [`litellm-agents`](litellm-agents/) | Register A2A agents, test them, control access, and use the kill switch. |
| [`litellm-guardrails`](litellm-guardrails/) | Create guardrails, attach them with policies to teams, keys, or tags, and test them. |
| [`litellm-budgets`](litellm-budgets/) | Reusable budgets, customer (end user) budgets, and who is close to their limit. |
| [`litellm-usage`](litellm-usage/) | Spend, tokens, and requests by user, team, org, key, tag, model, customer, or agent. |

Skills are written against LiteLLM v1.103 (September 2026) and note the version where recent behavior changed. Organization features, key tags, guardrails on keys, and key regeneration need a LiteLLM Enterprise license; the skills say so where it applies.

## Migrating from v1

v1 shipped one skill per action (`/add-key`, `/update-key`, `/delete-key`, ...). Each domain is now a single skill that covers every action, so `/add-key` becomes `/litellm-keys` (or just ask for what you want). Re-run `install.sh` and it removes the old links.

## Requirements

- `curl` and `python3`
- A reachable LiteLLM proxy with a database for admin features
- A proxy admin key for admin skills; a team admin key works for its own team

## Development

```bash
python3 -m unittest discover -s tests -v
```

Evals for the skills live in `evals/`. Each skill directory is self-contained so it can be installed on its own.

## License

MIT
