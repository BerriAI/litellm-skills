# litellm skills

[Agent Skills](https://agentskills.io) for managing live LiteLLM proxy deployments. Requires `curl`.

## Skills

### Users
| Skill | Description |
|-------|-------------|
| [`add-user`](add-user/) | Create a user with email, role, budget, and model access. |
| [`update-user`](update-user/) | Update budget, role, or model access for an existing user. |
| [`delete-user`](delete-user/) | Delete one or more users. |

### Teams
| Skill | Description |
|-------|-------------|
| [`add-team`](add-team/) | Create a team with budget and model limits. |
| [`update-team`](update-team/) | Update budget, models, or rate limits for an existing team. |
| [`delete-team`](delete-team/) | Delete one or more teams. |

### API Keys
| Skill | Description |
|-------|-------------|
| [`add-key`](add-key/) | Generate an API key scoped to a user, team, budget, and expiry. |
| [`update-key`](update-key/) | Update budget, models, or expiry for an existing key. |
| [`delete-key`](delete-key/) | Delete one or more API keys by value or alias. |

### Organizations
| Skill | Description |
|-------|-------------|
| [`add-org`](add-org/) | Create an organization with budget and model access. |
| [`delete-org`](delete-org/) | Delete one or more organizations. |

### Models
| Skill | Description |
|-------|-------------|
| [`add-model`](add-model/) | Add any LLM provider (OpenAI, Azure, Anthropic, Bedrock, Ollama…) and test it. |
| [`update-model`](update-model/) | Rotate credentials or change the underlying deployment for a model. |
| [`delete-model`](delete-model/) | Remove a model from the proxy. |

### MCP Servers
| Skill | Description |
|-------|-------------|
| [`add-mcp`](add-mcp/) | Register an MCP server (SSE, HTTP, or stdio). |
| [`update-mcp`](update-mcp/) | Update URL, credentials, or allowed tools for an MCP server. |
| [`delete-mcp`](delete-mcp/) | Remove an MCP server registration. |

### Agents
| Skill | Description |
|-------|-------------|
| [`add-agent`](add-agent/) | Create an AI agent backed by a model and optional MCP servers. |
| [`update-agent`](update-agent/) | Swap the model or update description and limits for an agent. |
| [`delete-agent`](delete-agent/) | Remove an agent. |

### Usage
| Skill | Description |
|-------|-------------|
| [`view-usage`](view-usage/) | Query daily spend and token activity by user, team, org, or model. |

## Install

```bash
git clone https://github.com/BerriAI/litellm-skills.git ~/.claude/skills/litellm
cd ~/.claude/skills
ln -s litellm/add-user add-user
ln -s litellm/update-user update-user
ln -s litellm/delete-user delete-user
ln -s litellm/add-team add-team
ln -s litellm/update-team update-team
ln -s litellm/delete-team delete-team
ln -s litellm/add-key add-key
ln -s litellm/update-key update-key
ln -s litellm/delete-key delete-key
ln -s litellm/add-org add-org
ln -s litellm/delete-org delete-org
ln -s litellm/add-model add-model
ln -s litellm/update-model update-model
ln -s litellm/delete-model delete-model
ln -s litellm/add-mcp add-mcp
ln -s litellm/update-mcp update-mcp
ln -s litellm/delete-mcp delete-mcp
ln -s litellm/add-agent add-agent
ln -s litellm/update-agent update-agent
ln -s litellm/delete-agent delete-agent
ln -s litellm/view-usage view-usage
```

Claude Code discovers skills by looking for `SKILL.md` files at `~/.claude/skills/<skill-name>/SKILL.md`. Since this is a multi-skill repo, symlinks are needed to expose each sub-skill at the expected depth.

## Requirements

- `curl` installed
- A running LiteLLM proxy
- A proxy admin key (not a virtual key scoped to `llm_api_routes`)

## License

MIT
