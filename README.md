# litellm skills

[Agent Skills](https://agentskills.io) for managing live LiteLLM proxy deployments. Requires `curl`.

## Skills

| Skill | Description |
|-------|-------------|
| [`manage-entities`](manage-entities/) | CRUD for users, teams, API keys, and organizations. |
| [`manage-models`](manage-models/) | Add, list, update, and delete models. Walks through provider + credentials. |
| [`view-usage`](view-usage/) | Query daily spend and token activity by user, team, org, or model. |

## Install

```bash
git clone https://github.com/BerriAI/litellm-skills.git ~/.claude/skills/litellm
cd ~/.claude/skills
ln -s litellm/manage-entities manage-entities
ln -s litellm/manage-models manage-models
ln -s litellm/view-usage view-usage
```

Claude Code discovers skills by looking for `SKILL.md` files at `~/.claude/skills/<skill-name>/SKILL.md`. Since this is a multi-skill repo, symlinks are needed to expose each sub-skill at the expected depth.

## Usage

Point the skills at any running LiteLLM proxy — local or remote. You'll be asked for your `LITELLM_BASE_URL` and an admin API key.

```
/manage-entities    # create a team, generate a key, add a user, etc.
/manage-models      # add gpt-4o, claude, ollama, azure — any provider
/view-usage         # see spend + token counts for today / this month / by team
```

## Requirements

- `curl` installed
- A running LiteLLM proxy
- An admin or master API key (not a virtual key scoped to `llm_api_routes`)

## License

MIT
