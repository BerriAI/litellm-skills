# litellm skills

[Agent Skills](https://agentskills.io) for managing live LiteLLM proxy deployments. Requires `curl`.

## Skills

| Skill | Description |
|-------|-------------|
| [`add-user`](add-user/) | Create a user with email, role, budget, and model access. |
| [`add-team`](add-team/) | Create a team with budget and model limits. |
| [`add-key`](add-key/) | Generate an API key scoped to a user, team, budget, and expiry. |
| [`add-org`](add-org/) | Create an organization with budget and model access. |
| [`add-model`](add-model/) | Add any LLM provider (OpenAI, Azure, Anthropic, Bedrock, Ollama…) and test it. |
| [`add-mcp`](add-mcp/) | Register an MCP server (SSE, HTTP, or stdio). |
| [`add-agent`](add-agent/) | Create an AI agent backed by a model and optional MCP servers. |
| [`view-usage`](view-usage/) | Query daily spend and token activity by user, team, org, or model. |

## Install

```bash
git clone https://github.com/BerriAI/litellm-skills.git ~/.claude/skills/litellm
cd ~/.claude/skills
ln -s litellm/add-user add-user
ln -s litellm/add-team add-team
ln -s litellm/add-key add-key
ln -s litellm/add-org add-org
ln -s litellm/add-model add-model
ln -s litellm/add-mcp add-mcp
ln -s litellm/add-agent add-agent
ln -s litellm/view-usage view-usage
```

Claude Code discovers skills by looking for `SKILL.md` files at `~/.claude/skills/<skill-name>/SKILL.md`. Since this is a multi-skill repo, symlinks are needed to expose each sub-skill at the expected depth.

## Usage

Point at any running LiteLLM proxy. You'll be asked for your `LITELLM_BASE_URL` and an admin key.

```
/add-user       → create a user
/add-team       → create a team
/add-key        → generate an API key
/add-org        → create an organization
/add-model      → add gpt-4o, claude, ollama, azure — any provider
/add-mcp        → register an MCP server
/add-agent      → create an AI agent
/view-usage     → see spend + token counts for today / this month / by team
```

## Requirements

- `curl` installed
- A running LiteLLM proxy
- A proxy admin key (not a virtual key scoped to `llm_api_routes`)

## License

MIT
